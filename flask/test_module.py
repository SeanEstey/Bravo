
import pymongo

client = pymongo.MongoClient('localhost', 27017)
db = client['test']

# Add imports for modules here to test for syntax error
# without having to run from flask

# import routing
