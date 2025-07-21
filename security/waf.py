"""
Web Application Firewall (WAF) Implementation
Provides advanced threat detection and protection against common web attacks
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple, Union

from flask import request, jsonify, g

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    """Threat severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionType(Enum):
    """WAF action types"""
    ALLOW = "allow"
    BLOCK = "block"
    CHALLENGE = "challenge"
    LOG = "log"
    RATE_LIMIT = "rate_limit"


@dataclass
class WAFRule:
    """WAF rule definition"""
    id: str
    name: str
    description: str
    pattern: Union[str, Pattern]
    threat_level: ThreatLevel
    action: ActionType
    enabled: bool = True
    score: int = 10
    category: str = "general"


@dataclass
class ThreatDetection:
    """Threat detection result"""
    detected: bool
    rule_id: str
    threat_level: ThreatLevel
    score: int
    message: str
    action: ActionType
    evidence: Dict[str, Any]


class RuleEngine:
    """WAF rule engine for pattern matching and threat detection"""
    
    def __init__(self):
        self.rules: Dict[str, WAFRule] = {}
        self.compiled_patterns: Dict[str, Pattern] = {}
        self._load_default_rules()
    
    def add_rule(self, rule: WAFRule) -> None:
        """Add a WAF rule"""
        self.rules[rule.id] = rule
        
        # Compile regex pattern if it's a string
        if isinstance(rule.pattern, str):
            try:
                self.compiled_patterns[rule.id] = re.compile(rule.pattern, re.IGNORECASE | re.MULTILINE)
            except re.error as e:
                logger.error(f"Invalid regex pattern in rule {rule.id}: {e}")
        else:
            self.compiled_patterns[rule.id] = rule.pattern
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a WAF rule"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            if rule_id in self.compiled_patterns:
                del self.compiled_patterns[rule_id]
            return True
        return False
    
    def evaluate_request(self, request_data: Dict[str, Any]) -> List[ThreatDetection]:
        """Evaluate request against all enabled rules"""
        detections = []
        
        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue
            
            detection = self._evaluate_rule(rule, request_data)
            if detection.detected:
                detections.append(detection)
        
        return detections
    
    def _evaluate_rule(self, rule: WAFRule, request_data: Dict[str, Any]) -> ThreatDetection:
        """Evaluate a single rule against request data"""
        pattern = self.compiled_patterns.get(rule.id)
        if not pattern:
            return ThreatDetection(
                detected=False,
                rule_id=rule.id,
                threat_level=rule.threat_level,
                score=0,
                message="Rule pattern not compiled",
                action=ActionType.LOG,
                evidence={}
            )
        
        # Check different parts of the request
        targets = [
            ("url", request_data.get("url", "")),
            ("query_string", request_data.get("query_string", "")),
            ("user_agent", request_data.get("user_agent", "")),
            ("referer", request_data.get("referer", "")),
            ("body", request_data.get("body", "")),
            ("headers", str(request_data.get("headers", {}))),
            ("cookies", str(request_data.get("cookies", {}))),
        ]
        
        for target_name, target_value in targets:
            if not target_value:
                continue
            
            match = pattern.search(str(target_value))
            if match:
                evidence = {
                    "target": target_name,
                    "matched_text": match.group(0),
                    "match_position": match.span(),
                    "full_text": target_value[:1000]  # Limit evidence size
                }
                
                return ThreatDetection(
                    detected=True,
                    rule_id=rule.id,
                    threat_level=rule.threat_level,
                    score=rule.score,
                    message=f"{rule.name}: {rule.description}",
                    action=rule.action,
                    evidence=evidence
                )
        
        return ThreatDetection(
            detected=False,
            rule_id=rule.id,
            threat_level=rule.threat_level,
            score=0,
            message="No match",
            action=ActionType.ALLOW,
            evidence={}
        )
    
    def _load_default_rules(self) -> None:
        """Load default WAF rules"""
        
        # SQL Injection Rules
        sql_injection_rules = [
            WAFRule(
                id="sqli_001",
                name="SQL Injection - UNION",
                description="Detects UNION-based SQL injection attempts",
                pattern=r"\b(union\s+(all\s+)?select)\b",
                threat_level=ThreatLevel.HIGH,
                action=ActionType.BLOCK,
                score=50,
                category="sql_injection"
            ),
            WAFRule(
                id="sqli_002",
                name="SQL Injection - Information Schema",
                description="Detects information schema access attempts",
                pattern=r"\b(information_schema|sysobjects|syscolumns)\b",
                threat_level=ThreatLevel.HIGH,
                action=ActionType.BLOCK,
                score=45,
                category="sql_injection"
            ),
            WAFRule(
                id="sqli_003",
                name="SQL Injection - Boolean Blind",
                description="Detects boolean-based blind SQL injection",
                pattern=r"(\s+(and|or)\s+\d+\s*=\s*\d+)|(\s+(and|or)\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?)",
                threat_level=ThreatLevel.MEDIUM,
                action=ActionType.BLOCK,
                score=35,
                category="sql_injection"
            ),
            WAFRule(
                id="sqli_004",
                name="SQL Injection - Time-based Blind",
                description="Detects time-based blind SQL injection",
                pattern=r"\b(sleep|waitfor\s+delay|benchmark|pg_sleep)\s*\(",
                threat_level=ThreatLevel.HIGH,
                action=ActionType.BLOCK,
                score=50,
                category="sql_injection"
            ),
        ]
        
        # XSS Rules
        xss_rules = [
            WAFRule(
                id="xss_001",
                name="XSS - Script Tags",
                description="Detects script tag injection attempts",
                pattern=r"<\s*script[^>]*>.*?</\s*script\s*>",
                threat_level=ThreatLevel.HIGH,
                action=ActionType.BLOCK,
                score=40,
                category="xss"
            ),
            WAFRule(
                id="xss_002",
                name="XSS - Event Handlers",
                description="Detects JavaScript event handler injection",
                pattern=r"\b(onload|onerror|onclick|onmouseover|onfocus|onblur)\s*=",
                threat_level=ThreatLevel.MEDIUM,
                action=ActionType.BLOCK,
                score=30,
                category="xss"
            ),
            WAFRule(
                id="xss_003",
                name="XSS - JavaScript Protocol",
                description="Detects javascript: protocol usage",
                pattern=r"javascript\s*:",
                threat_level=ThreatLevel.MEDIUM,
                action=ActionType.BLOCK,
                score=25,
                category="xss"
            ),
            WAFRule(
                id="xss_004",
                name="XSS - Data URLs",
                description="Detects potentially malicious data URLs",
                pattern=r"data\s*:\s*[^,]*script",
                threat_level=ThreatLevel.MEDIUM,
                action=ActionType.BLOCK,
                score=25,
                category="xss"
            ),
        ]
        
        # Path Traversal Rules
        path_traversal_rules = [
            WAFRule(
                id="path_001",
                name="Path Traversal - Directory Navigation",
                description="Detects directory traversal attempts",
                pattern=r"(\.\./){2,}|(\.\.\%2f){2,}|(\.\.\%5c){2,}",
                threat_level=ThreatLevel.HIGH,
                action=ActionType.BLOCK,
                score=40,
                category="path_traversal"
            ),
            WAFRule(
                id="path_002",
                name="Path Traversal - System Files",
                description="Detects attempts to access system files",
                pattern=r"\b(etc/passwd|etc/shadow|windows/system32|boot\.ini)\b",
                threat_level=ThreatLevel.CRITICAL,
                action=ActionType.BLOCK,
                score=60,
                category="path_traversal"
            ),
        ]
        
        # Command Injection Rules
        command_injection_rules = [
            WAFRule(
                id="cmd_001",
                name="Command Injection - System Commands",
                description="Detects system command injection attempts",
                pattern=r"\b(cat|ls|dir|ping|nslookup|dig|curl|wget|nc|netcat)\s+",
                threat_level=ThreatLevel.HIGH,
                action=ActionType.BLOCK,
                score=50,
                category="command_injection"
            ),
            WAFRule(
                id="cmd_002",
                name="Command Injection - Command Separators",
                description="Detects command separator usage",
                pattern=r"[;&|`$(){}[\]]",
                threat_level=ThreatLevel.MEDIUM,
                action=ActionType.LOG,  # Log only as it might be legitimate
                score=20,
                category="command_injection"
            ),
        ]
        
        # LDAP Injection Rules
        ldap_injection_rules = [
            WAFRule(
                id="ldap_001",
                name="LDAP Injection",
                description="Detects LDAP injection attempts",
                pattern=r"[()&|!*].*[()&|!*]",
                threat_level=ThreatLevel.MEDIUM,
                action=ActionType.BLOCK,
                score=30,
                category="ldap_injection"
            ),
        ]
        
        # XXE Rules
        xxe_rules = [
            WAFRule(
                id="xxe_001",
                name="XXE - External Entity",
                description="Detects XML External Entity injection",
                pattern=r"<!ENTITY[^>]*>",
                threat_level=ThreatLevel.HIGH,
                action=ActionType.BLOCK,
                score=45,
                category="xxe"
            ),
        ]
        
        # Scanning/Reconnaissance Rules
        scanning_rules = [
            WAFRule(
                id="scan_001",
                name="Scanner User Agent",
                description="Detects known security scanner user agents",
                pattern=r"\b(nmap|nikto|sqlmap|burp|nessus|acunetix|appscan|w3af|skipfish|wapiti|masscan|nuclei|gobuster|dirb|dirbuster|wfuzz|ffuf)\b",
                threat_level=ThreatLevel.HIGH,
                action=ActionType.BLOCK,
                score=40,
                category="scanning"
            ),
            WAFRule(
                id="scan_002",
                name="Directory Brute Force",
                description="Detects directory brute force patterns",
                pattern=r"/(admin|test|backup|config|old|tmp|temp|dev|staging|api)/",
                threat_level=ThreatLevel.LOW,
                action=ActionType.LOG,
                score=10,
                category="scanning"
            ),
        ]
        
        # Rate Limiting Bypass Rules
        rate_limit_rules = [
            WAFRule(
                id="rate_001",
                name="Rate Limit Bypass Headers",
                description="Detects rate limit bypass attempts using headers",
                pattern=r"x-forwarded-for|x-real-ip|x-originating-ip|x-cluster-client-ip",
                threat_level=ThreatLevel.LOW,
                action=ActionType.LOG,
                score=5,
                category="rate_limiting"
            ),
        ]
        
        # Load all rule sets
        all_rules = (
            sql_injection_rules + xss_rules + path_traversal_rules + 
            command_injection_rules + ldap_injection_rules + xxe_rules + 
            scanning_rules + rate_limit_rules
        )
        
        for rule in all_rules:
            self.add_rule(rule)
        
        logger.info(f"Loaded {len(all_rules)} default WAF rules")


class WAF:
    """Web Application Firewall main class"""
    
    def __init__(self):
        self.rule_engine = RuleEngine()
        self.blocked_ips: Set[str] = set()
        self.threat_scores: Dict[str, Dict[str, Any]] = {}
        self.enabled = True
        
        # Configuration
        self.block_threshold = 100  # Block IP if threat score exceeds this
        self.log_all_detections = True
        self.challenge_threshold = 50  # Challenge requests if score exceeds this
    
    def process_request(self) -> Optional[Tuple[Dict[str, Any], int]]:
        """Process incoming request through WAF"""
        if not self.enabled:
            return None
        
        client_ip = request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr)
        if "," in client_ip:
            client_ip = client_ip.split(",")[0].strip()
        
        # Check if IP is already blocked
        if client_ip in self.blocked_ips:
            logger.warning(f"Blocked IP {client_ip} attempted access")
            return {"error": "Access denied", "reason": "IP blocked"}, 403
        
        # Extract request data
        request_data = self._extract_request_data()
        
        # Evaluate request against rules
        detections = self.rule_engine.evaluate_request(request_data)
        
        if not detections:
            return None  # No threats detected, allow request
        
        # Process detections
        total_score = sum(detection.score for detection in detections)
        highest_threat = max(detections, key=lambda d: d.score)
        
        # Update threat score for IP
        self._update_threat_score(client_ip, total_score, detections)
        
        # Log detections
        if self.log_all_detections:
            self._log_detections(client_ip, detections, total_score)
        
        # Determine action based on highest threat level and score
        if highest_threat.action == ActionType.BLOCK or total_score >= self.block_threshold:
            # Block the request
            self._handle_block_action(client_ip, detections, total_score)
            return {
                "error": "Request blocked",
                "reason": "Security policy violation",
                "rule_id": highest_threat.rule_id
            }, 403
        
        elif total_score >= self.challenge_threshold:
            # Challenge the request (could implement CAPTCHA or similar)
            return {
                "error": "Security challenge required",
                "challenge_type": "verification",
                "message": "Please verify you are human"
            }, 429
        
        else:
            # Log but allow
            logger.info(f"Suspicious request from {client_ip}, score: {total_score}, allowing")
            return None
    
    def _extract_request_data(self) -> Dict[str, Any]:
        """Extract relevant data from Flask request object"""
        data = {
            "url": request.url,
            "path": request.path,
            "method": request.method,
            "query_string": request.query_string.decode("utf-8"),
            "user_agent": request.headers.get("User-Agent", ""),
            "referer": request.headers.get("Referer", ""),
            "content_type": request.headers.get("Content-Type", ""),
            "headers": dict(request.headers),
            "cookies": dict(request.cookies),
            "remote_addr": request.remote_addr,
        }
        
        # Get request body safely
        try:
            if request.is_json:
                data["body"] = json.dumps(request.get_json() or {})
            elif request.form:
                data["body"] = "&".join([f"{k}={v}" for k, v in request.form.items()])
            elif request.data:
                data["body"] = request.data.decode("utf-8", errors="ignore")[:10000]  # Limit size
        except Exception as e:
            logger.warning(f"Error extracting request body: {e}")
            data["body"] = ""
        
        return data
    
    def _update_threat_score(self, ip: str, score: int, detections: List[ThreatDetection]) -> None:
        """Update threat score for an IP address"""
        now = time.time()
        
        if ip not in self.threat_scores:
            self.threat_scores[ip] = {
                "total_score": 0,
                "detections": [],
                "first_seen": now,
                "last_seen": now
            }
        
        ip_data = self.threat_scores[ip]
        ip_data["total_score"] += score
        ip_data["last_seen"] = now
        
        # Keep recent detections (last hour)
        ip_data["detections"] = [
            d for d in ip_data["detections"]
            if now - d.get("timestamp", 0) < 3600
        ]
        
        # Add new detections
        for detection in detections:
            ip_data["detections"].append({
                "rule_id": detection.rule_id,
                "threat_level": detection.threat_level.value,
                "score": detection.score,
                "timestamp": now,
                "evidence": detection.evidence
            })
        
        # Auto-block if score is too high
        if ip_data["total_score"] >= self.block_threshold:
            self.blocked_ips.add(ip)
            logger.warning(f"IP {ip} auto-blocked due to high threat score: {ip_data['total_score']}")
    
    def _log_detections(self, ip: str, detections: List[ThreatDetection], total_score: int) -> None:
        """Log threat detections"""
        for detection in detections:
            logger.warning(
                f"WAF Detection - IP: {ip}, Rule: {detection.rule_id}, "
                f"Threat: {detection.threat_level.value}, Score: {detection.score}, "
                f"Message: {detection.message}, Evidence: {detection.evidence}"
            )
        
        if len(detections) > 1:
            logger.warning(f"Multiple threats detected from {ip}, total score: {total_score}")
    
    def _handle_block_action(self, ip: str, detections: List[ThreatDetection], score: int) -> None:
        """Handle block action"""
        logger.error(
            f"WAF BLOCK - IP: {ip}, Score: {score}, "
            f"Rules: {[d.rule_id for d in detections]}"
        )
        
        # Could implement additional actions here:
        # - Send alert to security team
        # - Update external firewall
        # - Add to threat intelligence feed
    
    def block_ip(self, ip: str) -> None:
        """Manually block an IP address"""
        self.blocked_ips.add(ip)
        logger.info(f"Manually blocked IP: {ip}")
    
    def unblock_ip(self, ip: str) -> bool:
        """Unblock an IP address"""
        if ip in self.blocked_ips:
            self.blocked_ips.remove(ip)
            logger.info(f"Unblocked IP: {ip}")
            return True
        return False
    
    def get_threat_report(self, ip: Optional[str] = None) -> Dict[str, Any]:
        """Get threat report for IP or all IPs"""
        if ip:
            return self.threat_scores.get(ip, {})
        
        return {
            "blocked_ips": list(self.blocked_ips),
            "threat_scores": self.threat_scores,
            "total_blocked": len(self.blocked_ips),
            "total_tracked": len(self.threat_scores)
        }


# Global WAF instance
waf = WAF()


def init_waf(app):
    """Initialize WAF with Flask app"""
    @app.before_request
    def waf_before_request():
        # Skip WAF for health checks and internal endpoints
        if request.path in ["/health", "/metrics"]:
            return None
        
        result = waf.process_request()
        if result:
            return jsonify(result[0]), result[1]
        return None
    
    logger.info("WAF initialized and active")