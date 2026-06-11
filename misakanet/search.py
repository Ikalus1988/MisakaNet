import re

def parse_query(query):
    # Remove consecutive spaces and punctuation
    query = re.sub(r'\s+', ' ', query)
    query = re.sub(r'[^\w\s]', '', query)
    
    # Remove emojis
    query = re.sub(r'[^\x00-\x7F]+', '', query)
    
    # Split query into keywords
    keywords = query.split()
    
    return keywords