```python
import logging

# Configure logging
logging.basicConfig(filename='app.log', 
                    filemode='a', 
                    format='%(asctime)s - %(levelname)s - %(message)s', 
                    level=logging.ERROR)

def divide_numbers(num1, num2):
    try:
        return num1 / num2
    except ZeroDivisionError as e:
        logging.error("Attempted to divide by zero: %s", e)
        return "Error: Cannot divide by zero."
    except TypeError as e:
        logging.error("Invalid type provided: %s", e)
        return "Error: Please provide numbers."
    except Exception as e:
        logging.error("An unexpected error occurred: %s", e)
        return "Error: An unexpected error occurred."

if __name__ == "__main__":
    result1 = divide_numbers(10, 2)
    print(result1)  # Should print 5.0

    result2 = divide_numbers(10, 0)
    print(result2)  # Should print error message

    result3 = divide_numbers(10, 'a')
    print(result3)  # Should print error message
```