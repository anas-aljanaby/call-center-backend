from supabase import create_client, Client
import os
import requests
from dotenv import load_dotenv
import json
import asyncio
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from time import time
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from models import ProcessingSettings
from src.services.transcription_service import ElevenLabsTranscriptionService

load_dotenv()
console = Console()

class CallProcessor:
    def __init__(self, skip_transcription=False):
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        self.api_url = "http://localhost:8000"
        self.bucket_name = 'call-recordings'
        self.skip_transcription = skip_transcription
        self.settings = ProcessingSettings()
        self.transcription_service = ElevenLabsTranscriptionService()
        
    def fetch_unprocessed_calls(self):
        """Fetch all unprocessed calls from the calls table"""
        console.print("[bold blue]Fetching unprocessed calls...[/bold blue]")
        response = self.supabase.table('calls') \
            .select('id, recording_url, organization_id') \
            .eq('processed', False) \
            .execute()
        console.print(f"[green]Found {len(response.data)} unprocessed calls[/green]")
        return response.data
        
    async def process_call(self, call_id: str, recording_url: str, organization_id: str):
        """Process a single call"""
        try:
            start_time = time()
            step_times = {}
            
            console.print(Panel(f"[bold cyan]Processing Call[/bold cyan]\nID: {call_id}\nURL: {recording_url}"))
            
            # Transcription step timing
            step_start = time()
            if self.skip_transcription:
                console.print("[yellow]Checking for existing transcription...[/yellow]")
                existing_analytics = self.supabase.table('call_analytics') \
                    .select('transcription') \
                    .eq('call_id', call_id) \
                    .execute()
                    
                if existing_analytics.data and existing_analytics.data[0].get('transcription'):
                    transcription_segments = existing_analytics.data[0]['transcription']
                    console.print("[green]✓ Using existing transcription[/green]")
                    step_times['transcription'] = time() - step_start
                    console.print(f"[blue]⏱ Transcription step took: {step_times['transcription']:.2f} seconds[/blue]")
                else:
                    console.print("[red]No existing transcription found. Will perform transcription.[/red]")
                    self.skip_transcription = False
            
            if not self.skip_transcription:
                # Download using the public URL directly
                console.print("[yellow]Downloading audio file...[/yellow]")
                response = requests.get(recording_url)
                response.raise_for_status()
                console.print("[green]✓ Audio file downloaded successfully[/green]")
                
                # Step 1: Transcribe using ElevenLabs
                console.print("\n[bold]Step 1: Transcribing audio with ElevenLabs[/bold]")
                language_code = "ara"  # Using Arabic as default based on previous settings
                num_speakers = 2
                
                console.print(f"Settings: language_code={language_code}, num_speakers={num_speakers}")
                
                # Use the ElevenLabs transcription service
                transcription_segments = self.transcription_service.transcribe_from_bytes(
                    audio_bytes=response.content,
                    language_code=language_code,
                    num_speakers=num_speakers
                )
                
                console.print("[green]✓ Transcription complete[/green]")
                console.print(Panel(
                    f"[cyan]Transcription Response:[/cyan]\n{json.dumps(transcription_segments, indent=2, ensure_ascii=False)}",
                    title="Transcription Result"
                ))
                step_times['transcription'] = time() - step_start
                console.print(f"[blue]⏱ Transcription step took: {step_times['transcription']:.2f} seconds[/blue]")
            
            # Step 2: Get events analysis
            console.print("\n[bold]Step 2: Analyzing events[/bold]")
            events_settings = {
                'segments': transcription_segments[:1],
                'settings': {
                    "aiModel": self.settings.eventsModel
                }
            }
            console.print(f"Settings: {json.dumps(events_settings, indent=2)}")
            
            step_start = time()
            events_response = requests.post(
                f"{self.api_url}/api/analyze-events",
                json={
                    'segments': transcription_segments,
                    'settings': {
                        "aiModel": self.settings.eventsModel
                    }
                }
            )
            events_data = events_response.json()
            console.print("[green]✓ Events analysis complete[/green]")
            console.print(Panel(
                f"[cyan]Events Response:[/cyan]\n{json.dumps(events_data, indent=2)}",
                title="Events Analysis Result"
            ))
            step_times['events_analysis'] = time() - step_start
            console.print(f"[blue]⏱ Events analysis took: {step_times['events_analysis']:.2f} seconds[/blue]")
            
            # Step 3: Get conversation summary
            console.print("\n[bold]Step 3: Generating conversation summary[/bold]")
            summary_settings = {
                'segments': transcription_segments[:1],
                'settings': {
                    "aiModel": self.settings.summaryModel
                }
            }
            console.print(f"Settings: {json.dumps(summary_settings, indent=2)}")
            
            step_start = time()
            summary_response = requests.post(
                f"{self.api_url}/api/summarize-conversation",
                json={
                    'segments': transcription_segments,
                    'settings': {
                        "aiModel": self.settings.summaryModel
                    }
                }
            )
            summary_data = summary_response.json()
            console.print("[green]✓ Summary generation complete[/green]")
            console.print(Panel(
                f"[cyan]Summary Response:[/cyan]\n{json.dumps(summary_data, indent=2)}",
                title="Summary Result"
            ))
            step_times['summary'] = time() - step_start
            console.print(f"[blue]⏱ Summary generation took: {step_times['summary']:.2f} seconds[/blue]")
            
            # Step 4: Get additional analytics
            console.print("\n[bold]Step 4: Analyzing call details[/bold]")
            details_settings = {
                'segments': transcription_segments[:1],
                'settings': {
                    "aiModel": self.settings.detailsModel
                }
            }
            console.print(f"Settings: {json.dumps(details_settings, indent=2)}")
            
            step_start = time()
            details_response = requests.post(
                f"{self.api_url}/api/analyze-call-details",
                json={
                    'segments': transcription_segments,
                    'settings': {
                        "aiModel": self.settings.detailsModel
                    }
                }
            )
            details_data = details_response.json()
            console.print("[green]✓ Call details analysis complete[/green]")
            console.print(Panel(
                f"[cyan]Details Response:[/cyan]\n{json.dumps(details_data, indent=2)}",
                title="Call Details Result"
            ))
            step_times['call_details'] = time() - step_start
            console.print(f"[blue]⏱ Call details analysis took: {step_times['call_details']:.2f} seconds[/blue]")
            
            # Update call_analytics table
            console.print("\n[bold]Step 5: Storing analytics data[/bold]")
            analytics_data = {
                'call_id': call_id,
                'sentiment_score': details_data.get('sentiment_score'),
                'transcription': transcription_segments,
                'transcript_highlights': events_data.get('key_events', []),
                'topics': details_data.get('topics', []),
                'flags': details_data.get('flags', []),
                'call_type': details_data.get('call_type', 'other'),
                'summary': summary_data.get('summary', '')
            }
            
            # Check if analytics record exists
            existing_record = self.supabase.table('call_analytics') \
                .select('*') \
                .eq('call_id', call_id) \
                .execute()
                
            if existing_record.data:
                # Update existing record
                self.supabase.table('call_analytics') \
                    .update(analytics_data) \
                    .eq('call_id', call_id) \
                    .execute()
                console.print("[green]✓ Analytics data updated successfully[/green]")
            else:
                # Insert new record
                self.supabase.table('call_analytics') \
                    .insert(analytics_data) \
                    .execute()
                console.print("[green]✓ Analytics data inserted successfully[/green]")
                
            # Mark call as processed
            self.supabase.table('calls') \
                .update({'processed': True}) \
                .eq('id', call_id) \
                .execute()
            console.print("[green]✓ Call marked as processed[/green]")
            
            console.print(Panel("[bold green]✓ Call Processing Complete[/bold green]", 
                              title=f"Call ID: {call_id}"))
            
            total_time = time() - start_time
            
            # Print timing summary
            console.print(Panel(
                "\n".join([
                    "[bold]Processing Time Summary[/bold]",
                    f"[cyan]Transcription:[/cyan] {step_times.get('transcription', 0):.2f}s",
                    f"[cyan]Events Analysis:[/cyan] {step_times.get('events_analysis', 0):.2f}s",
                    f"[cyan]Summary Generation:[/cyan] {step_times.get('summary', 0):.2f}s",
                    f"[cyan]Call Details Analysis:[/cyan] {step_times.get('call_details', 0):.2f}s",
                    f"[bold green]Total Processing Time:[/bold green] {total_time:.2f}s"
                ]),
                title="⏱ Timing Summary"
            ))
            
            return {
                'success': True,
                'call_id': call_id,
                'processing_time': total_time,
                'step_times': step_times
            }
            
        except Exception as e:
            total_time = time() - start_time
            console.print(f"[bold red]Error processing call {call_id}:[/bold red] {str(e)}")
            return {
                'success': False,
                'call_id': call_id,
                'error': str(e),
                'processing_time': total_time
            }
    
    async def process_all_calls(self):
        """Process all unprocessed calls"""
        unprocessed_calls = self.fetch_unprocessed_calls()
        if not unprocessed_calls:
            console.print("[yellow]No unprocessed calls found[/yellow]")
            return []
            
        console.print(f"\n[bold]Starting processing of {len(unprocessed_calls)} calls[/bold]")
        tasks = []
        
        for call in unprocessed_calls:
            task = asyncio.create_task(
                self.process_call(
                    call['id'], 
                    call['recording_url'],
                    call['organization_id']
                )
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # Print summary
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        
        console.print(Panel(
            f"[bold]Processing Summary[/bold]\n"
            f"Total Calls: {len(results)}\n"
            f"[green]✓ Successful: {successful}[/green]\n"
            f"[red]✗ Failed: {failed}[/red]"
        ))
        
        return results 