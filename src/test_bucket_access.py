from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

def test_bucket_access():
    supabase = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_KEY')
    )
    
    try:
        # List buckets
        buckets = supabase.storage.list_buckets()
        print("Available buckets:", buckets)
        
        # Try to list files in the call-recordings bucket
        files = supabase.storage.from_('call-recordings').list()
        print("Files in bucket:", files)
        
    except Exception as e:
        print(f"Error accessing bucket: {str(e)}")

if __name__ == "__main__":
    test_bucket_access()