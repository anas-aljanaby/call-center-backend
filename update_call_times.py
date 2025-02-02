from supabase import create_client
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import random
import pytz

def update_call_times():
    # Load environment variables
    load_dotenv()
    
    # Initialize Supabase client
    supabase = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_KEY')
    )
    
    # Get today's date
    today = datetime.now(pytz.UTC)
    
    # Set base time to 9 AM today
    base_time = today.replace(
        hour=9, 
        minute=0, 
        second=0, 
        microsecond=0
    )
    
    # Get all calls
    response = supabase.table('calls').select('id, duration, recording_url').execute()
    calls = response.data
    
    # Update each call with a random start time
    for call in calls:
        # Generate random minutes to add (between 0 and 8 hours)
        random_minutes = random.randint(0, 8 * 60)  # 8 hours in minutes
        
        # Calculate start time
        start_time = base_time + timedelta(minutes=random_minutes)
        
        # Calculate end time based on duration
        end_time = start_time + timedelta(seconds=call['duration'])
        
        # Convert signed URL to public URL
        recording_url = call['recording_url']
        if recording_url and '?' in recording_url:
            recording_url = recording_url.split('?')[0]
        
        # Update the record
        supabase.table('calls').update({
            'started_at': start_time.isoformat(),
            'ended_at': end_time.isoformat(),
            'recording_url': recording_url
        }).eq('id', call['id']).execute()
        
        print(f"Updated call {call['id']}: {start_time.strftime('%I:%M %p')}")

if __name__ == "__main__":
    update_call_times() 