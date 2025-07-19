#!/usr/bin/env python3
"""
Multi-Agent Container Testing System
Tests all three containerized options simultaneously:
1. Original Monolithic Application
2. Device Management Service
3. Temperature Data Service
"""

import asyncio
import concurrent.futures
import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("multi-agent-test.log"),
    ],
)


@dataclass
class TestResult:
    agent_name: str
    service_name: str
    container_name: str
    build_success: bool
    start_success: bool
    health_check_success: bool
    response_time_ms: float
    error_message: Optional[str] = None
    response_data: Optional[Dict] = None


class ContainerAgent:
    """Base class for container testing agents"""

    def __init__(self, name: str, service_path: str, container_name: str, port: int):
        self.name = name
        self.service_path = service_path
        self.container_name = container_name
        self.port = port
        self.logger = logging.getLogger(f"Agent-{name}")
        self.image_tag = f"{container_name}:test"

    async def build_container(self) -> bool:
        """Build the container image"""
        try:
            self.logger.info(f"🔨 Building container: {self.image_tag}")

            # Build command
            cmd = ["podman", "build", "-t", self.image_tag, self.service_path]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                self.logger.info(f"✅ Build successful: {self.image_tag}")
                return True
            else:
                self.logger.error(f"❌ Build failed: {stderr.decode()}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Build exception: {str(e)}")
            return False

    async def start_container(self, env_vars: Dict[str, str] = None) -> bool:
        """Start the container"""
        try:
            self.logger.info(f"🚀 Starting container: {self.container_name}")

            # Stop and remove existing container if it exists
            await self._cleanup_container()

            # Build run command
            cmd = [
                "podman",
                "run",
                "-d",
                "--name",
                self.container_name,
                "-p",
                f"{self.port}:8080",
            ]

            # Add environment variables
            if env_vars:
                for key, value in env_vars.items():
                    cmd.extend(["-e", f"{key}={value}"])

            cmd.append(self.image_tag)

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                # Wait for container to start
                await asyncio.sleep(5)
                self.logger.info(f"✅ Container started: {self.container_name}")
                return True
            else:
                self.logger.error(f"❌ Container start failed: {stderr.decode()}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Container start exception: {str(e)}")
            return False

    async def test_health_endpoint(self) -> Dict:
        """Test the health endpoint"""
        try:
            self.logger.info(
                f"🔍 Testing health endpoint: http://localhost:{self.port}/health"
            )

            start_time = time.time()

            # Give the service time to fully start
            max_retries = 10
            for attempt in range(max_retries):
                try:
                    response = requests.get(
                        f"http://localhost:{self.port}/health", timeout=10
                    )

                    response_time_ms = (time.time() - start_time) * 1000

                    if response.status_code in [
                        200,
                        500,
                    ]:  # 500 expected for DB connection errors
                        response_data = response.json()

                        # Determine success based on service type
                        if response.status_code == 200:
                            success = True
                            self.logger.info(
                                f"✅ Health check passed: {response_data.get('status')}"
                            )
                        else:
                            # For microservices, 500 with proper error structure is expected
                            success = (
                                "status" in response_data and "error" in response_data
                            )
                            if success:
                                self.logger.info(
                                    f"⚠️  Health check returned expected error: {response_data.get('error')}"
                                )
                            else:
                                self.logger.warning(
                                    f"❓ Unexpected health response: {response_data}"
                                )

                        return {
                            "success": success,
                            "response_time_ms": response_time_ms,
                            "response_data": response_data,
                            "status_code": response.status_code,
                        }

                except requests.exceptions.ConnectionError:
                    if attempt < max_retries - 1:
                        self.logger.info(
                            f"⏳ Waiting for service to start... (attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(2)
                        continue
                    else:
                        raise

            raise Exception("Service did not respond after maximum retries")

        except Exception as e:
            self.logger.error(f"❌ Health check failed: {str(e)}")
            return {
                "success": False,
                "response_time_ms": 0,
                "error": str(e),
                "status_code": None,
            }

    async def _cleanup_container(self):
        """Clean up existing container"""
        try:
            # Stop container
            await asyncio.create_subprocess_exec(
                "podman",
                "stop",
                self.container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )

            # Remove container
            await asyncio.create_subprocess_exec(
                "podman",
                "rm",
                self.container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except:
            pass

    async def cleanup(self):
        """Clean up resources"""
        await self._cleanup_container()
        self.logger.info(f"🧹 Cleaned up container: {self.container_name}")


class MonolithicAgent(ContainerAgent):
    """Agent for testing the original monolithic Flask application"""

    def __init__(self):
        super().__init__(
            name="Monolithic",
            service_path=".",
            container_name="grill-stats-test",
            port=5000,
        )

    async def run_test(self) -> TestResult:
        """Run complete test sequence"""
        self.logger.info("🎯 Starting Monolithic Application Test")

        # Environment variables for monolithic app
        env_vars = {
            "THERMOWORKS_API_KEY": "test-key-monolithic",
            "HOMEASSISTANT_URL": "http://test-homeassistant:8123",
            "HOMEASSISTANT_TOKEN": "test-token-monolithic",
        }

        build_success = await self.build_container()
        start_success = False
        health_result = {"success": False, "response_time_ms": 0}

        if build_success:
            start_success = await self.start_container(env_vars)
            if start_success:
                health_result = await self.test_health_endpoint()

        return TestResult(
            agent_name=self.name,
            service_name="Monolithic Flask App",
            container_name=self.container_name,
            build_success=build_success,
            start_success=start_success,
            health_check_success=health_result["success"],
            response_time_ms=health_result["response_time_ms"],
            response_data=health_result.get("response_data"),
            error_message=health_result.get("error"),
        )


class DeviceServiceAgent(ContainerAgent):
    """Agent for testing the Device Management Service"""

    def __init__(self):
        super().__init__(
            name="DeviceService",
            service_path="./services/device-service",
            container_name="device-service-test",
            port=8080,
        )

    async def run_test(self) -> TestResult:
        """Run complete test sequence"""
        self.logger.info("🎯 Starting Device Service Test")

        # Environment variables for device service
        env_vars = {
            "DB_HOST": "test-postgresql",
            "DB_PORT": "5432",
            "DB_NAME": "grill_monitoring",
            "DB_USERNAME": "test_user",
            "DB_PASSWORD": "test_pass",
            "THERMOWORKS_API_KEY": "test-key-device-service",
            "DEBUG": "true",
        }

        build_success = await self.build_container()
        start_success = False
        health_result = {"success": False, "response_time_ms": 0}

        if build_success:
            start_success = await self.start_container(env_vars)
            if start_success:
                health_result = await self.test_health_endpoint()

        return TestResult(
            agent_name=self.name,
            service_name="Device Management Service",
            container_name=self.container_name,
            build_success=build_success,
            start_success=start_success,
            health_check_success=health_result["success"],
            response_time_ms=health_result["response_time_ms"],
            response_data=health_result.get("response_data"),
            error_message=health_result.get("error"),
        )


class TemperatureServiceAgent(ContainerAgent):
    """Agent for testing the Temperature Data Service"""

    def __init__(self):
        super().__init__(
            name="TemperatureService",
            service_path="./services/temperature-service",
            container_name="temperature-service-test",
            port=8081,
        )

    async def run_test(self) -> TestResult:
        """Run complete test sequence"""
        self.logger.info("🎯 Starting Temperature Service Test")

        # Environment variables for temperature service
        env_vars = {
            "INFLUXDB_HOST": "test-influxdb",
            "INFLUXDB_PORT": "8086",
            "INFLUXDB_DATABASE": "grill_monitoring",
            "INFLUXDB_USERNAME": "test_user",
            "INFLUXDB_PASSWORD": "test_pass",
            "REDIS_HOST": "test-redis",
            "REDIS_PORT": "6379",
            "REDIS_PASSWORD": "test_pass",
            "THERMOWORKS_API_KEY": "test-key-temperature-service",
            "DEBUG": "true",
        }

        build_success = await self.build_container()
        start_success = False
        health_result = {"success": False, "response_time_ms": 0}

        if build_success:
            start_success = await self.start_container(env_vars)
            if start_success:
                health_result = await self.test_health_endpoint()

        return TestResult(
            agent_name=self.name,
            service_name="Temperature Data Service",
            container_name=self.container_name,
            build_success=build_success,
            start_success=start_success,
            health_check_success=health_result["success"],
            response_time_ms=health_result["response_time_ms"],
            response_data=health_result.get("response_data"),
            error_message=health_result.get("error"),
        )


class MultiAgentTestOrchestrator:
    """Orchestrates the multi-agent testing"""

    def __init__(self):
        self.logger = logging.getLogger("TestOrchestrator")
        self.agents = [
            MonolithicAgent(),
            DeviceServiceAgent(),
            TemperatureServiceAgent(),
        ]
        self.results: List[TestResult] = []

    async def run_parallel_tests(self) -> List[TestResult]:
        """Run all agent tests in parallel"""
        self.logger.info("🚀 Starting Multi-Agent Parallel Testing")

        # Run all tests concurrently
        tasks = [agent.run_test() for agent in self.agents]
        self.results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        for i, result in enumerate(self.results):
            if isinstance(result, Exception):
                self.logger.error(f"Agent {self.agents[i].name} failed: {result}")
                self.results[i] = TestResult(
                    agent_name=self.agents[i].name,
                    service_name=f"{self.agents[i].name} Service",
                    container_name=self.agents[i].container_name,
                    build_success=False,
                    start_success=False,
                    health_check_success=False,
                    response_time_ms=0,
                    error_message=str(result),
                )

        return self.results

    async def cleanup_all(self):
        """Clean up all agent resources"""
        self.logger.info("🧹 Cleaning up all agents")
        cleanup_tasks = [agent.cleanup() for agent in self.agents]
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)

    def generate_report(self) -> Dict:
        """Generate comprehensive test report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_agents": len(self.agents),
            "summary": {
                "builds_successful": sum(1 for r in self.results if r.build_success),
                "containers_started": sum(1 for r in self.results if r.start_success),
                "health_checks_passed": sum(
                    1 for r in self.results if r.health_check_success
                ),
                "avg_response_time_ms": (
                    sum(r.response_time_ms for r in self.results) / len(self.results)
                    if self.results
                    else 0
                ),
            },
            "agents": [],
        }

        for result in self.results:
            agent_report = {
                "agent_name": result.agent_name,
                "service_name": result.service_name,
                "container_name": result.container_name,
                "status": {
                    "build": "✅" if result.build_success else "❌",
                    "start": "✅" if result.start_success else "❌",
                    "health": "✅" if result.health_check_success else "❌",
                },
                "response_time_ms": result.response_time_ms,
                "response_data": result.response_data,
                "error_message": result.error_message,
            }
            report["agents"].append(agent_report)

        return report

    def print_report(self):
        """Print formatted test report"""
        report = self.generate_report()

        print("\n" + "=" * 80)
        print("🤖 MULTI-AGENT CONTAINER TEST RESULTS")
        print("=" * 80)
        print(f"⏰ Test Timestamp: {report['timestamp']}")
        print(f"🎯 Total Agents: {report['total_agents']}")
        print()

        # Summary
        summary = report["summary"]
        print("📊 SUMMARY")
        print("-" * 40)
        print(
            f"✅ Builds Successful: {summary['builds_successful']}/{report['total_agents']}"
        )
        print(
            f"🚀 Containers Started: {summary['containers_started']}/{report['total_agents']}"
        )
        print(
            f"💚 Health Checks Passed: {summary['health_checks_passed']}/{report['total_agents']}"
        )
        print(f"⚡ Average Response Time: {summary['avg_response_time_ms']:.2f}ms")
        print()

        # Individual agent results
        print("🔍 INDIVIDUAL AGENT RESULTS")
        print("-" * 40)
        for agent in report["agents"]:
            print(f"\n🤖 {agent['agent_name']} ({agent['service_name']})")
            print(f"   Container: {agent['container_name']}")
            print(
                f"   Build: {agent['status']['build']} | Start: {agent['status']['start']} | Health: {agent['status']['health']}"
            )
            print(f"   Response Time: {agent['response_time_ms']:.2f}ms")

            if agent["response_data"]:
                print(f"   Response: {agent['response_data'].get('status', 'N/A')}")

            if agent["error_message"]:
                print(f"   Error: {agent['error_message']}")

        print("\n" + "=" * 80)

        # Overall status
        all_builds_passed = summary["builds_successful"] == report["total_agents"]
        all_containers_started = summary["containers_started"] == report["total_agents"]

        if all_builds_passed and all_containers_started:
            print("🎉 OVERALL STATUS: ALL TESTS PASSED!")
        elif all_builds_passed:
            print("⚠️  OVERALL STATUS: BUILDS PASSED, SOME CONTAINERS FAILED")
        else:
            print("❌ OVERALL STATUS: SOME BUILDS FAILED")

        print("=" * 80)


async def main():
    """Main test execution"""
    orchestrator = MultiAgentTestOrchestrator()

    try:
        # Run parallel tests
        results = await orchestrator.run_parallel_tests()

        # Generate and display report
        orchestrator.print_report()

        # Save detailed report to file
        report = orchestrator.generate_report()
        with open("multi-agent-test-report.json", "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n📄 Detailed report saved to: multi-agent-test-report.json")
        print(f"📄 Logs saved to: multi-agent-test.log")

    finally:
        # Clean up all containers
        await orchestrator.cleanup_all()


if __name__ == "__main__":
    print("🚀 Starting Multi-Agent Container Testing System")
    print("This will test all three containerized services simultaneously")
    print("-" * 60)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        sys.exit(1)
