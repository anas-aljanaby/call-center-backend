from supabase import create_client, Client
import os
from dotenv import load_dotenv
from typing import List, Dict
import random

load_dotenv()

class AgentManager:
    def __init__(self, organization_id: str):
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        self.organization_id = organization_id
    
    def get_existing_agents(self) -> List[Dict]:
        """Get existing agents for the organization"""
        try:
            response = self.supabase.table('agents') \
                .select('*') \
                .eq('organization_id', self.organization_id) \
                .execute()
            return response.data
        except Exception as e:
            print(f"Error fetching existing agents: {str(e)}")
            return []
    
    def get_random_agent(self) -> Dict:
        """Get a random agent from the organization"""
        agents = self.get_existing_agents()
        if not agents:
            raise ValueError("No agents found for this organization")
        return random.choice(agents)
    
    def create_agent(self, email: str, full_name: str) -> Dict:
        """Create a new agent for the organization"""
        try:
            # Check if agent with this email already exists
            existing = self.supabase.table('agents') \
                .select('*') \
                .eq('email', email) \
                .execute()
            
            if existing.data:
                return {
                    'success': True,
                    'agent': existing.data[0],
                    'existing': True
                }
            
            response = self.supabase.table('agents').insert({
                'organization_id': self.organization_id,
                'email': email,
                'full_name': full_name,
                'role': 'agent',
                'status': 'active'
            }).execute()
            
            return {
                'success': True,
                'agent': response.data[0] if response.data else None,
                'existing': False
            }
        except Exception as e:
            print(f"Error creating agent: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }