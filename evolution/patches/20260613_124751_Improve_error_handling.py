```python
import logging

class AssistNeo:
    def __init__(self):
        self.logger = self.setup_logger()

    def setup_logger(self):
        logger = logging.getLogger("AssistNeo")
        logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler("assist_neo_errors.log")
        handler.setLevel(logging.ERROR)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def handle_request(self, request):
        try:
            # Process the request
            response = self.process_request(request)
            return response
        except Exception as e:
            self.log_error(e, request)
            self.send_error_response()

    def process_request(self, request):
        # Simulating request processing that might cause an error
        if not isinstance(request, str):
            raise ValueError("Request must be a string.")
        # Continue with processing...
        return "Processed request successfully."

    def log_error(self, error, request):
        error_message = f"Error processing request: {error}, Request: {request}"
        self.logger.error(error_message)

    def send_error_response(self):
        return "An error occurred while processing your request. Please try again later."
```