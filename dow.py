import sys
import re
from datetime import datetime

def add_day_of_week():
    date_pattern = re.compile(r'(\d{4}-\d{2}-\d{2}).?.?</h1>')
    
    for line in sys.stdin:
        match = date_pattern.search(line)
        if match:
            date_str = match.group(1)
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                day_of_week = date_obj.strftime('%a')
                line = line.replace('</h1>', f'</h1><h2>{day_of_week}</h2>')
            except ValueError:
                sys.stderr.write(f"oops: {date_str}")
        sys.stdout.write(line)

if __name__ == "__main__":
    add_day_of_week()
