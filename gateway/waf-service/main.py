import os
import re
import time
import json
import base64
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

import redis
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import structlog

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "3"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
BLOCK_MALICIOUS_IPS = os.getenv("BLOCK_MALICIOUS_IPS", "true").lower() == "true"
RATE_LIMIT_SUSPICIOUS = os.getenv("RATE_LIMIT_SUSPICIOUS", "true").lower() == "true"

# Logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Redis setup
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

# Metrics
waf_requests = Counter('waf_requests_total', 'Total WAF requests', ['action'])
waf_blocks = Counter('waf_blocks_total', 'Total WAF blocks', ['rule_type'])
waf_duration = Histogram('waf_processing_duration_seconds', 'WAF processing duration')
active_rules = Gauge('waf_active_rules', 'Number of active WAF rules')

# Models
class WAFAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    CHALLENGE = "challenge"
    LOG = "log"

class WAFRuleType(str, Enum):
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    PATH_TRAVERSAL = "path_traversal"
    COMMAND_INJECTION = "command_injection"
    CSRF = "csrf"
    FILE_INCLUSION = "file_inclusion"
    PROTOCOL_VIOLATION = "protocol_violation"
    ANOMALY_DETECTION = "anomaly_detection"
    IP_REPUTATION = "ip_reputation"
    RATE_LIMITING = "rate_limiting"

class WAFRule(BaseModel):
    id: str
    name: str
    description: str
    rule_type: WAFRuleType
    pattern: str
    action: WAFAction
    enabled: bool = True
    severity: int = 5  # 1-10 scale
    tags: List[str] = []
    custom_message: Optional[str] = None

class WAFResult(BaseModel):
    action: WAFAction
    matched_rules: List[Dict[str, Any]]
    risk_score: int
    processing_time_ms: float
    reason: Optional[str] = None

# FastAPI app
app = FastAPI(
    title="WAF Service",
    description="Web Application Firewall for API Gateway",
    version="1.0.0"
)

class WebApplicationFirewall:
    def __init__(self):
        self.redis = redis_client
        self.rules = self._load_default_rules()
        self.custom_rules = self._load_custom_rules()
        
        # Compile regex patterns for better performance
        self.compiled_patterns = {}
        self._compile_patterns()
    
    def _load_default_rules(self) -> List[WAFRule]:
        """Load default WAF rules"""
        return [
            # SQL Injection Rules
            WAFRule(
                id="sql_001",
                name="SQL Injection - Union Select",
                description="Detects UNION SELECT statements",
                rule_type=WAFRuleType.SQL_INJECTION,
                pattern=r'(?i)\bunion\s+select\b',
                action=WAFAction.BLOCK,
                severity=9,
                tags=["sql", "injection", "union"]
            ),
            WAFRule(
                id="sql_002",
                name="SQL Injection - Drop Table",
                description="Detects DROP TABLE statements",
                rule_type=WAFRuleType.SQL_INJECTION,
                pattern=r'(?i)\bdrop\s+table\b',
                action=WAFAction.BLOCK,
                severity=10,
                tags=["sql", "injection", "drop"]
            ),
            WAFRule(
                id="sql_003",
                name="SQL Injection - Comments",
                description="Detects SQL comments used in injection",
                rule_type=WAFRuleType.SQL_INJECTION,
                pattern=r'(?i)(--|\#|\/\*|\*\/)',
                action=WAFAction.LOG,
                severity=6,
                tags=["sql", "injection", "comments"]
            ),
            
            # XSS Rules
            WAFRule(
                id="xss_001",
                name="XSS - Script Tags",
                description="Detects script tags",
                rule_type=WAFRuleType.XSS,
                pattern=r'(?i)<script[^>]*>',
                action=WAFAction.BLOCK,
                severity=8,
                tags=["xss", "script"]
            ),
            WAFRule(
                id="xss_002",
                name="XSS - JavaScript Events",
                description="Detects JavaScript event handlers",
                rule_type=WAFRuleType.XSS,
                pattern=r'(?i)on(load|error|click|focus|blur)\s*=',
                action=WAFAction.BLOCK,
                severity=7,
                tags=["xss", "events"]
            ),
            WAFRule(
                id="xss_003",
                name="XSS - JavaScript Protocol",
                description="Detects javascript: protocol",
                rule_type=WAFRuleType.XSS,
                pattern=r'(?i)javascript:',
                action=WAFAction.BLOCK,
                severity=8,
                tags=["xss", "javascript"]
            ),
            
            # Path Traversal Rules
            WAFRule(
                id="path_001",
                name="Path Traversal - Directory Traversal",
                description="Detects directory traversal attempts",
                rule_type=WAFRuleType.PATH_TRAVERSAL,
                pattern=r'(?i)(\.\.\/|\.\.\\)',
                action=WAFAction.BLOCK,
                severity=8,
                tags=["path", "traversal"]
            ),
            WAFRule(
                id="path_002",
                name="Path Traversal - Encoded Traversal",
                description="Detects encoded directory traversal",
                rule_type=WAFRuleType.PATH_TRAVERSAL,
                pattern=r'(?i)(%2e%2e%2f|%2e%2e\\)',
                action=WAFAction.BLOCK,
                severity=8,
                tags=["path", "traversal", "encoded"]
            ),
            WAFRule(
                id="path_003",
                name="Path Traversal - System Files",
                description="Detects access to system files",
                rule_type=WAFRuleType.PATH_TRAVERSAL,
                pattern=r'(?i)(\/etc\/passwd|\/proc\/|boot\.ini|system32)',
                action=WAFAction.BLOCK,
                severity=9,
                tags=["path", "traversal", "system"]
            ),
            
            # Command Injection Rules
            WAFRule(
                id="cmd_001",
                name="Command Injection - Shell Commands",
                description="Detects shell command injection",
                rule_type=WAFRuleType.COMMAND_INJECTION,
                pattern=r'(?i)(;\s*(cat|ls|rm|cp|mv|chmod|ps|kill|wget|curl)\s)',
                action=WAFAction.BLOCK,
                severity=9,
                tags=["command", "injection", "shell"]
            ),
            WAFRule(
                id="cmd_002",
                name="Command Injection - Command Operators",
                description="Detects command chaining operators",
                rule_type=WAFRuleType.COMMAND_INJECTION,
                pattern=r'(\|\||&&|;|\|)',
                action=WAFAction.LOG,
                severity=5,
                tags=["command", "injection", "operators"]
            ),
            
            # Protocol Violation Rules
            WAFRule(
                id="proto_001",
                name="Protocol Violation - Null Bytes",
                description="Detects null byte injection",
                rule_type=WAFRuleType.PROTOCOL_VIOLATION,
                pattern=r'%00',
                action=WAFAction.BLOCK,
                severity=7,
                tags=["protocol", "null", "byte"]
            ),
            WAFRule(
                id="proto_002",
                name="Protocol Violation - HTTP Request Smuggling",
                description="Detects HTTP request smuggling attempts",
                rule_type=WAFRuleType.PROTOCOL_VIOLATION,
                pattern=r'(?i)(transfer-encoding:\s*chunked.*content-length:|content-length:.*transfer-encoding:\s*chunked)',
                action=WAFAction.BLOCK,
                severity=8,
                tags=["protocol", "smuggling"]
            ),
        ]
    
    def _load_custom_rules(self) -> List[WAFRule]:
        """Load custom rules from Redis"""
        try:
            custom_rules = []
            rule_keys = self.redis.keys("waf_rule:*")
            
            for rule_key in rule_keys:
                rule_data = self.redis.get(rule_key)
                if rule_data:
                    try:
                        rule_dict = json.loads(rule_data)
                        custom_rules.append(WAFRule(**rule_dict))
                    except Exception as e:
                        logger.error("Failed to load custom rule", rule_key=rule_key, error=str(e))
            
            logger.info("Loaded custom WAF rules", count=len(custom_rules))
            return custom_rules
            
        except Exception as e:
            logger.error("Failed to load custom rules", error=str(e))
            return []
    
    def _compile_patterns(self):
        """Compile regex patterns for better performance"""
        all_rules = self.rules + self.custom_rules
        
        for rule in all_rules:
            if rule.enabled:
                try:
                    self.compiled_patterns[rule.id] = re.compile(rule.pattern)
                except re.error as e:
                    logger.error("Invalid regex pattern", rule_id=rule.id, pattern=rule.pattern, error=str(e))
        
        active_rules.set(len(self.compiled_patterns))
    
    def add_custom_rule(self, rule: WAFRule):
        """Add a custom WAF rule"""
        try:
            # Store in Redis
            rule_key = f"waf_rule:{rule.id}"
            self.redis.set(rule_key, rule.json())
            
            # Add to memory
            self.custom_rules.append(rule)
            
            # Compile pattern
            if rule.enabled:
                try:
                    self.compiled_patterns[rule.id] = re.compile(rule.pattern)
                    active_rules.set(len(self.compiled_patterns))
                except re.error as e:
                    logger.error("Invalid regex pattern", rule_id=rule.id, error=str(e))
            
            logger.info("Custom WAF rule added", rule_id=rule.id)
            
        except Exception as e:
            logger.error("Failed to add custom rule", rule_id=rule.id, error=str(e))
            raise
    
    def remove_custom_rule(self, rule_id: str):
        """Remove a custom WAF rule"""
        try:
            # Remove from Redis
            rule_key = f"waf_rule:{rule_id}"
            self.redis.delete(rule_key)
            
            # Remove from memory
            self.custom_rules = [r for r in self.custom_rules if r.id != rule_id]
            
            # Remove compiled pattern
            if rule_id in self.compiled_patterns:
                del self.compiled_patterns[rule_id]
                active_rules.set(len(self.compiled_patterns))
            
            logger.info("Custom WAF rule removed", rule_id=rule_id)
            
        except Exception as e:
            logger.error("Failed to remove custom rule", rule_id=rule_id, error=str(e))
            raise
    
    def analyze_request(self, 
                       method: str,
                       path: str,
                       headers: Dict[str, str],
                       query_params: Dict[str, str],
                       body: Optional[str] = None,
                       ip_address: Optional[str] = None) -> WAFResult:
        """Analyze request against WAF rules"""
        start_time = time.time()
        matched_rules = []
        total_risk_score = 0
        
        try:
            # Combine all request data for analysis
            request_data = {
                "path": path,
                "query": urllib.parse.urlencode(query_params) if query_params else "",
                "headers": json.dumps(headers),
                "body": body or "",
                "method": method
            }
            
            # URL decode for better pattern matching
            decoded_data = {}
            for key, value in request_data.items():
                if isinstance(value, str):
                    try:
                        decoded_data[key] = urllib.parse.unquote(value)
                    except:
                        decoded_data[key] = value
                else:
                    decoded_data[key] = value
            
            # Check each compiled pattern
            all_rules = self.rules + self.custom_rules
            rule_lookup = {rule.id: rule for rule in all_rules}
            
            for rule_id, compiled_pattern in self.compiled_patterns.items():
                rule = rule_lookup.get(rule_id)
                if not rule or not rule.enabled:
                    continue
                
                # Check pattern against each part of the request
                for data_type, data_value in decoded_data.items():
                    if data_value and compiled_pattern.search(str(data_value)):
                        match_info = {
                            "rule_id": rule.id,
                            "rule_name": rule.name,
                            "rule_type": rule.rule_type.value,
                            "action": rule.action.value,
                            "severity": rule.severity,
                            "matched_in": data_type,
                            "pattern": rule.pattern,
                            "tags": rule.tags
                        }
                        matched_rules.append(match_info)
                        total_risk_score += rule.severity
                        
                        # Log the match
                        logger.warning("WAF rule matched", 
                                     rule_id=rule.id, 
                                     rule_name=rule.name,
                                     matched_in=data_type,
                                     ip_address=ip_address)
                        
                        # Update metrics
                        waf_blocks.labels(rule_type=rule.rule_type.value).inc()
                        
                        break  # Only count first match per rule
            
            # Determine final action
            final_action = WAFAction.ALLOW
            reason = None
            
            if matched_rules:
                # Check for any BLOCK actions
                block_rules = [r for r in matched_rules if r["action"] == "block"]
                if block_rules:
                    final_action = WAFAction.BLOCK
                    reason = f"Blocked by {len(block_rules)} rule(s)"
                    waf_requests.labels(action="block").inc()
                else:
                    # Check for CHALLENGE actions
                    challenge_rules = [r for r in matched_rules if r["action"] == "challenge"]
                    if challenge_rules:
                        final_action = WAFAction.CHALLENGE
                        reason = f"Challenge triggered by {len(challenge_rules)} rule(s)"
                        waf_requests.labels(action="challenge").inc()
                    else:
                        waf_requests.labels(action="log").inc()
            else:
                waf_requests.labels(action="allow").inc()
            
            processing_time = (time.time() - start_time) * 1000
            waf_duration.observe(processing_time / 1000)
            
            return WAFResult(
                action=final_action,
                matched_rules=matched_rules,
                risk_score=min(total_risk_score, 100),  # Cap at 100
                processing_time_ms=processing_time,
                reason=reason
            )
            
        except Exception as e:
            logger.error("WAF analysis failed", error=str(e))
            processing_time = (time.time() - start_time) * 1000
            
            return WAFResult(
                action=WAFAction.ALLOW,  # Allow on error to avoid blocking legitimate traffic
                matched_rules=[],
                risk_score=0,
                processing_time_ms=processing_time,
                reason=f"Analysis error: {str(e)}"
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get WAF statistics"""
        try:
            total_rules = len(self.rules) + len(self.custom_rules)
            enabled_rules = len(self.compiled_patterns)
            
            rule_types = {}
            all_rules = self.rules + self.custom_rules
            for rule in all_rules:
                if rule.enabled:
                    rule_types[rule.rule_type.value] = rule_types.get(rule.rule_type.value, 0) + 1
            
            return {
                "total_rules": total_rules,
                "enabled_rules": enabled_rules,
                "disabled_rules": total_rules - enabled_rules,
                "rule_types": rule_types,
                "default_rules": len(self.rules),
                "custom_rules": len(self.custom_rules)
            }
            
        except Exception as e:
            logger.error("Failed to get WAF statistics", error=str(e))
            return {"error": "Failed to retrieve statistics"}

# Global WAF instance
waf = WebApplicationFirewall()

# Routes
@app.get("/health")
async def health_check():
    try:
        redis_client.ping()
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unavailable")

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/analyze")
async def analyze_request(
    method: str,
    path: str,
    headers: Dict[str, str] = {},
    query_params: Dict[str, str] = {},
    body: Optional[str] = None,
    ip_address: Optional[str] = None
):
    """Analyze request against WAF rules"""
    try:
        result = waf.analyze_request(method, path, headers, query_params, body, ip_address)
        return result.dict()
    except Exception as e:
        logger.error("WAF analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/rules")
async def add_rule(rule: WAFRule):
    """Add a custom WAF rule"""
    try:
        waf.add_custom_rule(rule)
        return {"message": "Rule added successfully", "rule_id": rule.id}
    except Exception as e:
        logger.error("Failed to add rule", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/rules/{rule_id}")
async def remove_rule(rule_id: str):
    """Remove a custom WAF rule"""
    try:
        waf.remove_custom_rule(rule_id)
        return {"message": "Rule removed successfully", "rule_id": rule_id}
    except Exception as e:
        logger.error("Failed to remove rule", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/rules")
async def get_rules():
    """Get all WAF rules"""
    try:
        all_rules = []
        
        # Add default rules
        for rule in waf.rules:
            rule_dict = rule.dict()
            rule_dict["source"] = "default"
            all_rules.append(rule_dict)
        
        # Add custom rules
        for rule in waf.custom_rules:
            rule_dict = rule.dict()
            rule_dict["source"] = "custom"
            all_rules.append(rule_dict)
        
        return {"rules": all_rules}
    except Exception as e:
        logger.error("Failed to get rules", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/statistics")
async def get_statistics():
    """Get WAF statistics"""
    try:
        stats = waf.get_statistics()
        return stats
    except Exception as e:
        logger.error("Failed to get statistics", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/rule-types")
async def get_rule_types():
    """Get available WAF rule types"""
    return {
        "rule_types": [
            {
                "name": rule_type.value,
                "description": rule_type.value.replace("_", " ").title()
            }
            for rule_type in WAFRuleType
        ]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)