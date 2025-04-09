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
import logging
import datetime
import uuid

sys.path.append(str(Path(__file__).parent.parent.parent))
from models import ProcessingSettings
from src.services.transcription_service import ElevenLabsTranscriptionService

load_dotenv()
console = Console()

class CallProcessor:
    def __init__(self, skip_transcription=False, collect_stats=False):
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        self.api_url = "http://localhost:8000"
        self.bucket_name = 'call-recordings'
        self.skip_transcription = skip_transcription
        self.collect_stats = collect_stats
        self.settings = ProcessingSettings()
        self.transcription_service = ElevenLabsTranscriptionService(api_key=os.getenv('ELEVENLABS_API_KEY'))
        
        # Set up logging
        self.setup_logging()
        
    def setup_logging(self):
        """Set up the logging system with file and console handlers"""
        # Create logs directory if it doesn't exist
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Create a unique run ID and timestamp for this processing run
        self.run_id = str(uuid.uuid4())[:8]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_filename = f"call_processing_{timestamp}_{self.run_id}.log"
        
        # Set up the file logger for detailed logs
        self.file_logger = logging.getLogger(f"call_processor.file.{self.run_id}")
        self.file_logger.setLevel(logging.DEBUG)
        
        # Create file handler
        file_handler = logging.FileHandler(logs_dir / self.log_filename)
        file_handler.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # Add handlers to logger
        self.file_logger.addHandler(file_handler)
        
        # Prevent propagation to root logger
        self.file_logger.propagate = False
        
        # Log run start
        self.file_logger.info(f"=== Starting new processing run {self.run_id} ===")
        self.file_logger.info(f"Skip transcription: {self.skip_transcription}")
        self.file_logger.info(f"Collect stats: {self.collect_stats}")
        
        # Log to console
        console.print(f"[bold blue]Starting processing run [/bold blue][bold green]{self.run_id}[/bold green]")
        console.print(f"[blue]Detailed logs will be saved to: [/blue][cyan]{logs_dir / self.log_filename}[/cyan]")
        
    def fetch_unprocessed_calls(self, limit=None):
        """Fetch unprocessed calls from the calls table with optional limit"""
        console.print("[bold blue]Fetching unprocessed calls...[/bold blue]")
        self.file_logger.info("Fetching unprocessed calls")
        
        query = self.supabase.table('calls') \
            .select('id, recording_url, organization_id') \
            .eq('processed', False)
        
        # Apply limit if specified
        if limit is not None:
            query = query.limit(limit)
            self.file_logger.info(f"Limiting to {limit} calls")
        
        response = query.execute()
        call_count = len(response.data)
        
        console.print(f"[green]Found {call_count} unprocessed calls[/green]")
        self.file_logger.info(f"Found {call_count} unprocessed calls")
        
        if limit is not None and call_count > 0:
            console.print(f"[yellow]Limited to processing {limit} calls[/yellow]")
        
        return response.data
        
    async def process_call(self, call_id: str, recording_url: str, organization_id: str):
        """Process a single call"""
        # Create a call-specific logger
        call_logger = logging.getLogger(f"call_processor.call.{call_id}")
        call_logger.setLevel(logging.DEBUG)
        call_logger.addHandler(logging.FileHandler(Path("logs") / self.log_filename))
        call_logger.propagate = False
        
        try:
            start_time = time()
            step_times = {}
            
            # Log to file
            call_logger.info(f"=== Processing call {call_id} ===")
            call_logger.info(f"Recording URL: {recording_url}")
            call_logger.info(f"Organization ID: {organization_id}")
            
            # Log to console
            console.print(Panel(f"[bold cyan]Processing Call[/bold cyan]\nID: {call_id}\nURL: {recording_url}"))
            
            # Transcription step timing
            step_start = time()
            if self.skip_transcription:
                console.print("[yellow]Checking for existing transcription...[/yellow]")
                call_logger.info("Checking for existing transcription")
                
                existing_analytics = self.supabase.table('call_analytics') \
                    .select('transcription') \
                    .eq('call_id', call_id) \
                    .execute()
                
                call_logger.debug(f"Existing analytics query response: {json.dumps(existing_analytics.data)}")
                    
                if existing_analytics.data and existing_analytics.data[0].get('transcription'):
                    transcription_segments = existing_analytics.data[0]['transcription']
                    console.print("[green]✓ Using existing transcription[/green]")
                    call_logger.info("Using existing transcription")
                    step_times['transcription'] = time() - step_start
                    console.print(f"[blue]⏱ Transcription step took: {step_times['transcription']:.2f} seconds[/blue]")
                else:
                    console.print("[red]No existing transcription found. Will perform transcription.[/red]")
                    call_logger.info("No existing transcription found. Will perform transcription.")
                    self.skip_transcription = False
            
            if not self.skip_transcription:
                # Download using the public URL directly
                console.print("[yellow]Downloading audio file...[/yellow]")
                call_logger.info("Downloading audio file")
                
                response = requests.get(recording_url)
                response.raise_for_status()
                
                console.print("[green]✓ Audio file downloaded successfully[/green]")
                call_logger.info("Audio file downloaded successfully")
                
                # Step 1: Transcribe using ElevenLabs
                console.print("\n[bold]Step 1: Transcribing audio with ElevenLabs[/bold]")
                call_logger.info("Step 1: Transcribing audio with ElevenLabs")
                
                language_code = "ara"  # Using Arabic as default based on previous settings
                num_speakers = 2
                
                console.print(f"Settings: language_code={language_code}, num_speakers={num_speakers}")
                call_logger.info(f"Transcription settings: language_code={language_code}, num_speakers={num_speakers}")
                
                # Use the ElevenLabs transcription service
                call_logger.info("Sending transcription request to ElevenLabs")
                transcription_segments = self.transcription_service.transcribe_from_bytes(
                    audio_bytes=response.content,
                    language_code=language_code,
                    num_speakers=num_speakers
                )
                
                console.print("[green]✓ Transcription complete[/green]")
                call_logger.info("Transcription complete")
                
                # Check if only one speaker was detected
                speaker_ids = set()
                for segment in transcription_segments:
                    if 'speaker' in segment:
                        speaker_ids.add(segment['speaker'])
                
                # If only one speaker was detected, retry with 3 speakers
                if len(speaker_ids) <= 1 and num_speakers == 2:
                    console.print("[yellow]Only one speaker detected. Retrying transcription with 3 speakers...[/yellow]")
                    call_logger.warning("Only one speaker detected. Retrying transcription with 3 speakers")
                    
                    # Update num_speakers for retry
                    num_speakers = 3
                    
                    # Retry transcription with 3 speakers
                    call_logger.info("Sending transcription request to ElevenLabs with 3 speakers")
                    transcription_segments = self.transcription_service.transcribe_from_bytes(
                        audio_bytes=response.content,
                        language_code=language_code,
                        num_speakers=num_speakers
                    )
                    
                    console.print("[green]✓ Retry transcription complete[/green]")
                    call_logger.info("Retry transcription complete")
                    
                    # Check speakers after retry
                    retry_speaker_ids = set()
                    for segment in transcription_segments:
                        if 'speaker' in segment:
                            retry_speaker_ids.add(segment['speaker'])
                    
                    console.print(f"[cyan]Speakers detected after retry: {len(retry_speaker_ids)}[/cyan]")
                    call_logger.info(f"Speakers detected after retry: {len(retry_speaker_ids)}")
                
                # Log detailed transcription result to file only
                call_logger.debug(f"Transcription response: {json.dumps(transcription_segments, ensure_ascii=False)}")
                
                # Log summary to console
                console.print(f"[cyan]Transcription segments: {len(transcription_segments)}[/cyan]")
                
                step_times['transcription'] = time() - step_start
                console.print(f"[blue]⏱ Transcription step took: {step_times['transcription']:.2f} seconds[/blue]")
                call_logger.info(f"Transcription step took: {step_times['transcription']:.2f} seconds")
            
            # Step 2: Get events analysis
            console.print("\n[bold]Step 2: Analyzing events[/bold]")
            call_logger.info("Step 2: Analyzing events")
            
            events_settings = {
                'segments': transcription_segments[:1],
                'settings': {
                    "aiModel": self.settings.eventsModel
                }
            }
            console.print(f"Settings: Using model {self.settings.eventsModel}")
            call_logger.info(f"Events analysis settings: {json.dumps(events_settings)}")
            
            step_start = time()
            call_logger.info("Sending events analysis request")
            
            events_request = {
                'segments': transcription_segments,
                'settings': {
                    "aiModel": self.settings.eventsModel
                }
            }
            call_logger.debug(f"Events analysis request: {json.dumps(events_request)}")
            
            events_response = requests.post(
                f"{self.api_url}/api/analyze-events",
                json=events_request
            )
            events_data = events_response.json()
            
            console.print("[green]✓ Events analysis complete[/green]")
            call_logger.info("Events analysis complete")
            
            # Log detailed events data to file only
            call_logger.debug(f"Events analysis response: {json.dumps(events_data)}")
            
            # Log summary to console
            key_events_count = len(events_data.get('key_events', []))
            console.print(f"[cyan]Key events identified: {key_events_count}[/cyan]")
            
            step_times['events_analysis'] = time() - step_start
            console.print(f"[blue]⏱ Events analysis took: {step_times['events_analysis']:.2f} seconds[/blue]")
            call_logger.info(f"Events analysis took: {step_times['events_analysis']:.2f} seconds")
            
            # Step 3: Get conversation summary
            console.print("\n[bold]Step 3: Generating conversation summary[/bold]")
            call_logger.info("Step 3: Generating conversation summary")
            
            summary_settings = {
                'segments': transcription_segments[:1],
                'settings': {
                    "aiModel": self.settings.summaryModel
                }
            }
            console.print(f"Settings: Using model {self.settings.summaryModel}")
            call_logger.info(f"Summary settings: {json.dumps(summary_settings)}")
            
            step_start = time()
            call_logger.info("Sending summary request")
            
            summary_request = {
                'segments': transcription_segments,
                'settings': {
                    "aiModel": self.settings.summaryModel
                }
            }
            call_logger.debug(f"Summary request: {json.dumps(summary_request)}")
            
            summary_response = requests.post(
                f"{self.api_url}/api/summarize-conversation",
                json=summary_request
            )
            summary_data = summary_response.json()
            
            console.print("[green]✓ Summary generation complete[/green]")
            call_logger.info("Summary generation complete")
            
            # Log detailed summary to file only
            call_logger.debug(f"Summary response: {json.dumps(summary_data)}")
            
            # Log summary preview to console
            summary_preview = summary_data.get('summary', '')[:100] + '...' if len(summary_data.get('summary', '')) > 100 else summary_data.get('summary', '')
            console.print(f"[cyan]Summary preview: {summary_preview}[/cyan]")
            
            step_times['summary'] = time() - step_start
            console.print(f"[blue]⏱ Summary generation took: {step_times['summary']:.2f} seconds[/blue]")
            call_logger.info(f"Summary generation took: {step_times['summary']:.2f} seconds")
            
            # Step 4: Get additional analytics
            console.print("\n[bold]Step 4: Analyzing call details[/bold]")
            call_logger.info("Step 4: Analyzing call details")
            
            details_settings = {
                'segments': transcription_segments[:1],
                'settings': {
                    "aiModel": self.settings.detailsModel
                }
            }
            console.print(f"Settings: Using model {self.settings.detailsModel}")
            call_logger.info(f"Call details settings: {json.dumps(details_settings)}")
            
            step_start = time()
            call_logger.info("Sending call details analysis request")
            
            details_request = {
                'segments': transcription_segments,
                'settings': {
                    "aiModel": self.settings.detailsModel
                }
            }
            call_logger.debug(f"Call details request: {json.dumps(details_request)}")
            
            details_response = requests.post(
                f"{self.api_url}/api/analyze-call-details",
                json=details_request
            )
            details_data = details_response.json()
            
            console.print("[green]✓ Call details analysis complete[/green]")
            call_logger.info("Call details analysis complete")
            
            # Log detailed call details to file only
            call_logger.debug(f"Call details response: {json.dumps(details_data)}")
            
            # Log summary to console
            sentiment_score = details_data.get('sentiment_score', 'N/A')
            topics_count = len(details_data.get('topics', []))
            flags_count = len(details_data.get('flags', []))
            console.print(f"[cyan]Sentiment score: {sentiment_score}, Topics: {topics_count}, Flags: {flags_count}[/cyan]")
            
            step_times['call_details'] = time() - step_start
            console.print(f"[blue]⏱ Call details analysis took: {step_times['call_details']:.2f} seconds[/blue]")
            call_logger.info(f"Call details analysis took: {step_times['call_details']:.2f} seconds")
            
            # Update call_analytics table
            console.print("\n[bold]Step 5: Storing analytics data[/bold]")
            call_logger.info("Step 5: Storing analytics data")
            
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
            
            call_logger.debug(f"Existing record check response: {json.dumps(existing_record.data)}")
                
            if existing_record.data:
                # Update existing record
                call_logger.info("Updating existing analytics record")
                self.supabase.table('call_analytics') \
                    .update(analytics_data) \
                    .eq('call_id', call_id) \
                    .execute()
                console.print("[green]✓ Analytics data updated successfully[/green]")
                call_logger.info("Analytics data updated successfully")
            else:
                # Insert new record
                call_logger.info("Inserting new analytics record")
                self.supabase.table('call_analytics') \
                    .insert(analytics_data) \
                    .execute()
                console.print("[green]✓ Analytics data inserted successfully[/green]")
                call_logger.info("Analytics data inserted successfully")
                
            # Mark call as processed
            call_logger.info("Marking call as processed")
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.supabase.table('calls') \
                .update({'processed': True, 'updated_at': now}) \
                .eq('id', call_id) \
                .execute()
            console.print("[green]✓ Call marked as processed[/green]")
            call_logger.info("Call marked as processed")
            
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
            
            call_logger.info(f"=== Call {call_id} processing completed in {total_time:.2f}s ===")
            
            return {
                'success': True,
                'call_id': call_id,
                'processing_time': total_time,
                'step_times': step_times
            }
            
        except Exception as e:
            total_time = time() - start_time if 'start_time' in locals() else 0
            console.print(f"[bold red]Error processing call {call_id}:[/bold red] {str(e)}")
            call_logger.error(f"Error processing call {call_id}: {str(e)}", exc_info=True)
            return {
                'success': False,
                'call_id': call_id,
                'error': str(e),
                'processing_time': total_time
            }
    
    async def process_all_calls(self, limit=None):
        """Process unprocessed calls with optional limit"""
        self.file_logger.info(f"Starting process_all_calls with limit={limit}")
        
        unprocessed_calls = self.fetch_unprocessed_calls(limit)
        if not unprocessed_calls:
            console.print("[yellow]No unprocessed calls found[/yellow]")
            self.file_logger.info("No unprocessed calls found")
            return []
            
        console.print(f"\n[bold]Starting processing of {len(unprocessed_calls)} calls[/bold]")
        self.file_logger.info(f"Starting processing of {len(unprocessed_calls)} calls")
        
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
        
        self.file_logger.info(f"Processing completed. Total: {len(results)}, Successful: {successful}, Failed: {failed}")
        
        # Calculate and display detailed stats if enabled
        if self.collect_stats and results:
            self._display_detailed_stats(results)
        
        return results

    def _display_detailed_stats(self, results):
        """Calculate and display detailed statistics about the processing run"""
        self.file_logger.info("Calculating detailed statistics")
        
        # Initialize stats
        total_processing_time = sum(r.get('processing_time', 0) for r in results)
        total_audio_duration = 0
        step_times = {
            'transcription': 0,
            'events_analysis': 0,
            'summary': 0,
            'call_details': 0
        }
        
        # Collect stats from each result
        for result in results:
            if not result.get('success'):
                continue
            
            # Add up step times
            for step, time_value in result.get('step_times', {}).items():
                step_times[step] = step_times.get(step, 0) + time_value
            
            # Get call duration from Supabase
            if 'call_id' in result:
                call_response = self.supabase.table('calls') \
                    .select('duration') \
                    .eq('id', result['call_id']) \
                    .execute()
                
                if call_response.data and 'duration' in call_response.data[0]:
                    total_audio_duration += call_response.data[0]['duration']
        
        # Calculate averages
        avg_processing_time = total_processing_time / len(results) if results else 0
        avg_step_times = {step: time_value / len(results) for step, time_value in step_times.items()}
        
        # Format durations for display
        total_minutes = total_audio_duration / 60
        processing_ratio = total_processing_time / total_audio_duration if total_audio_duration > 0 else 0
        
        # Log stats to file
        self.file_logger.info(f"Total Audio Duration: {total_minutes:.2f} minutes ({total_audio_duration:.2f} seconds)")
        self.file_logger.info(f"Average Call Duration: {(total_audio_duration / len(results)):.2f} seconds" if results else "No results")
        self.file_logger.info(f"Total Processing Time: {total_processing_time:.2f} seconds")
        self.file_logger.info(f"Average Processing Time: {avg_processing_time:.2f} seconds per call")
        self.file_logger.info(f"Processing-to-Audio Ratio: {processing_ratio:.2f}x realtime")
        self.file_logger.info(f"Step Breakdown (Total / Average):")
        self.file_logger.info(f"  Transcription: {step_times['transcription']:.2f}s / {avg_step_times['transcription']:.2f}s")
        self.file_logger.info(f"  Events Analysis: {step_times['events_analysis']:.2f}s / {avg_step_times['events_analysis']:.2f}s")
        self.file_logger.info(f"  Summary Generation: {step_times['summary']:.2f}s / {avg_step_times['summary']:.2f}s")
        self.file_logger.info(f"  Call Details Analysis: {step_times['call_details']:.2f}s / {avg_step_times['call_details']:.2f}s")
        
        # Display detailed stats to console
        console.print(Panel(
            "\n".join([
                "[bold cyan]Detailed Processing Statistics[/bold cyan]",
                "",
                f"[bold]Audio Content:[/bold]",
                f"Total Audio Duration: {total_minutes:.2f} minutes ({total_audio_duration:.2f} seconds)",
                f"Average Call Duration: {(total_audio_duration / len(results)):.2f} seconds" if results else "",
                "",
                f"[bold]Processing Performance:[/bold]",
                f"Total Processing Time: {total_processing_time:.2f} seconds",
                f"Average Processing Time: {avg_processing_time:.2f} seconds per call",
                f"Processing-to-Audio Ratio: {processing_ratio:.2f}x realtime",
                "",
                f"[bold]Step Breakdown (Total / Average):[/bold]",
                f"Transcription: {step_times['transcription']:.2f}s / {avg_step_times['transcription']:.2f}s",
                f"Events Analysis: {step_times['events_analysis']:.2f}s / {avg_step_times['events_analysis']:.2f}s",
                f"Summary Generation: {step_times['summary']:.2f}s / {avg_step_times['summary']:.2f}s",
                f"Call Details Analysis: {step_times['call_details']:.2f}s / {avg_step_times['call_details']:.2f}s",
            ]),
            title="📊 Processing Statistics",
            border_style="blue"
        ))

    async def fetch_call_by_id(self, call_id):
        """Fetch a specific call by ID"""
        console.print(f"[bold blue]Fetching call with ID: {call_id}[/bold blue]")
        self.file_logger.info(f"Fetching call with ID: {call_id}")
        
        response = self.supabase.table('calls') \
            .select('id, recording_url, storage_path, organization_id, processed') \
            .eq('id', call_id) \
            .execute()
        
        if not response.data:
            console.print(f"[red]Call with ID {call_id} not found[/red]")
            self.file_logger.error(f"Call with ID {call_id} not found")
            return None
        
        call_info = response.data[0]
        console.print(f"[green]Found call: {call_id}[/green]")
        self.file_logger.info(f"Found call: {call_id}, processed: {call_info['processed']}")
        
        # Generate a fresh signed URL
        try:
            # If storage_path exists, use it
            if call_info.get('storage_path'):
                bucket_name, file_name = call_info['storage_path'].split('/', 1)
            # Otherwise try to extract from recording_url
            elif call_info.get('recording_url'):
                url_parts = call_info['recording_url'].split('/storage/v1/object/sign/')[1].split('?')[0]
                bucket_name, file_name = url_parts.split('/', 1)
                
                # Update the storage_path for future use
                self.supabase.table('calls').update({
                    'storage_path': f"{bucket_name}/{file_name}"
                }).eq('id', call_id).execute()
                self.file_logger.info(f"Updated storage_path for call {call_id}")
            else:
                self.file_logger.error("No recording URL or storage path available")
                return call_info
            
            # Generate fresh URL
            fresh_url = self.supabase.storage.from_(bucket_name).create_signed_url(
                file_name,
                60 * 60  # 1 hour expiry
            )['signedURL']
            call_info['recording_url'] = fresh_url
            self.file_logger.info("Generated fresh signed URL for file access")
        except Exception as e:
            self.file_logger.error(f"Failed to generate fresh URL: {str(e)}")
        
        return call_info

    def _display_single_call_stats(self, result):
        """Display statistics for a single call"""
        self.file_logger.info("Calculating statistics for single call")
        
        # Get call duration from Supabase
        call_response = self.supabase.table('calls') \
            .select('duration') \
            .eq('id', result['call_id']) \
            .execute()
        
        if not call_response.data or 'duration' not in call_response.data[0]:
            console.print("[yellow]Could not retrieve call duration[/yellow]")
            self.file_logger.warning("Could not retrieve call duration")
            return
        
        duration = call_response.data[0]['duration']
        processing_time = result.get('processing_time', 0)
        step_times = result.get('step_times', {})
        
        # Calculate processing ratio
        processing_ratio = processing_time / duration if duration > 0 else 0
        
        # Log stats to file
        self.file_logger.info(f"Call Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        self.file_logger.info(f"Processing Time: {processing_time:.2f} seconds")
        self.file_logger.info(f"Processing-to-Audio Ratio: {processing_ratio:.2f}x realtime")
        self.file_logger.info("Step Breakdown:")
        for step, time_value in step_times.items():
            self.file_logger.info(f"  {step}: {time_value:.2f}s")
        
        # Display stats to console
        console.print(Panel(
            "\n".join([
                "[bold cyan]Call Processing Statistics[/bold cyan]",
                "",
                f"[bold]Audio Content:[/bold]",
                f"Call Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)",
                "",
                f"[bold]Processing Performance:[/bold]",
                f"Total Processing Time: {processing_time:.2f} seconds",
                f"Processing-to-Audio Ratio: {processing_ratio:.2f}x realtime",
                "",
                f"[bold]Step Breakdown:[/bold]",
                f"Transcription: {step_times.get('transcription', 0):.2f}s",
                f"Events Analysis: {step_times.get('events_analysis', 0):.2f}s",
                f"Summary Generation: {step_times.get('summary', 0):.2f}s",
                f"Call Details Analysis: {step_times.get('call_details', 0):.2f}s",
            ]),
            title="📊 Call Processing Statistics",
            border_style="blue"
        )) 