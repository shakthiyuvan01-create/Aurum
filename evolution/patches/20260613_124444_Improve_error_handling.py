```python
import logging

# Configure logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

def divide_numbers(num1, num2):
    try:
        result = num1 / num2
        return result
    except ZeroDivisionError as e:
        logging.error("Attempted to divide by zero: %s", e)
        return None
    except TypeError as e:
        logging.error("Invalid type provided: %s", e)
        return None
    except Exception as e:
        logging.error("An unexpected error occurred: %s", e)
        return None

if __name__ == "__main__":
    print(divide_numbers(10, 2))  # Should print 5.0
    print(divide_numbers(10, 0))  # Should log an error and return None
    print(divide_numbers(10, "a"))  # Should log an error and return None
```
