# Alternative approach - Remove OpenTelemetry complexity for now
# Replace the OpenTelemetry imports with a simple tracer class

class SimpleTracer:
    """Simple tracer for development/testing"""
    def start_as_current_span(self, name):
        class SimpleSpan:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        return SimpleSpan()

# Replace these lines in main.py:
# trace.set_tracer_provider(TracerProvider())
# tracer = trace.get_tracer(__name__)

# With:
tracer = SimpleTracer()

# This allows the service to start without OpenTelemetry complexity
# Full observability can be re-added once the core functionality works