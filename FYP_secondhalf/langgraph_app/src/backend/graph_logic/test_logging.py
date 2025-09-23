# test_logging.py
import logging
import sys

# Configure logging exactly as in your main file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_debug.log')
    ]
)

logger = logging.getLogger(__name__)
logger.debug("This debug should appear")
logger.info("This info should appear")
print("This print should appear", flush=True)

if __name__ == "__main__":
    print("Running test directly...")