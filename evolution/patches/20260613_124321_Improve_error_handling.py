```python
import logging

# Configure logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

def read_file(file_path):
    """Reads the content of a file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        return None
    except IOError as e:
        logging.error(f"An I/O error occurred: {e}")
        return None


def divide_numbers(num1, num2):
    """Divides num1 by num2."""
    try:
        return num1 / num2
    except ZeroDivisionError:
        logging.error("Attempted to divide by zero.")
        return None
    except TypeError:
        logging.error("Invalid input types: divisors must be numbers.")
        return None


def main():
    file_content = read_file('example.txt')
    if file_content is not None:
        print("File content successfully read.")
    
    result = divide_numbers(10, 0)  # This will trigger an error
    if result is not None:
        print(f"Division result: {result}")

if __name__ == "__main__":
    main()
```