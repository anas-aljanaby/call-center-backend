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
        # Check documents bucket
        print("\nTesting 'documents' bucket:")
        try:
            files = supabase.storage.from_('documents').list()
            print("✓ Documents bucket accessible")
            print("Files:", files)
            
            # Test upload
            test_file = 'test.txt'
            with open(test_file, 'w') as f:
                f.write('test content')
            
            with open(test_file, 'rb') as f:
                try:
                    response = supabase.storage.from_('documents').upload(
                        'test.txt',
                        f,
                        file_options={"contentType": "text/plain", "upsert": "true"}
                    )
                    print("✓ Test file upload successful")
                    
                    # Try to get URL
                    url = supabase.storage.from_('documents').get_public_url('test.txt')
                    print("✓ Public URL retrieved:", url)
                except Exception as upload_error:
                    print(f"✗ Upload test failed: {str(upload_error)}")
            
            # Clean up
            os.remove(test_file)
            
        except Exception as e:
            print(f"✗ Error accessing documents bucket: {str(e)}")
            
    except Exception as e:
        print(f"Error in test: {str(e)}")

if __name__ == "__main__":
    test_bucket_access()