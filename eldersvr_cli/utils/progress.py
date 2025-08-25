"""
Progress display utilities for EldersVR CLI
"""

import sys
import time
import os
from typing import Optional, Dict, Any, List
from threading import Lock


class ProgressBar:
    """Simple progress bar for command line operations"""
    
    def __init__(self, total: int, description: str = "", width: int = 50):
        self.total = total
        self.current = 0
        self.description = description
        self.width = width
        self.start_time = time.time()
        self.last_update = 0
    
    def update(self, amount: int = 1):
        """Update progress by specified amount"""
        self.current = min(self.current + amount, self.total)
        self._display()
    
    def set_progress(self, current: int):
        """Set current progress value"""
        self.current = min(max(current, 0), self.total)
        self._display()
    
    def _display(self):
        """Display the progress bar"""
        if self.total == 0:
            return
            
        # Calculate progress
        progress = self.current / self.total
        filled_width = int(self.width * progress)
        
        # Create progress bar
        bar = "█" * filled_width + "░" * (self.width - filled_width)
        
        # Calculate elapsed time and ETA
        elapsed = time.time() - self.start_time
        if progress > 0 and self.current < self.total:
            eta = elapsed / progress * (1 - progress)
            eta_str = f" ETA: {self._format_time(eta)}"
        else:
            eta_str = ""
        
        # Format output
        percent = progress * 100
        elapsed_str = self._format_time(elapsed)
        
        output = f"\r{self.description} |{bar}| {percent:.1f}% ({self.current}/{self.total}) [{elapsed_str}{eta_str}]"
        
        # Print with carriage return to overwrite
        sys.stdout.write(output)
        sys.stdout.flush()
        
        # Add newline when complete
        if self.current >= self.total:
            sys.stdout.write("\n")
    
    def _format_time(self, seconds: float) -> str:
        """Format time in human readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds/3600:.1f}h"
    
    def finish(self):
        """Complete the progress bar"""
        self.current = self.total
        self._display()


class TransferProgress:
    """Progress tracker for device transfers with real-time text percentages"""
    
    def __init__(self):
        self.devices: Dict[str, Dict[str, Any]] = {}
        self.last_update_time = 0
        self.update_interval = 0.1  # Update every 100ms for real-time feel
    
    def add_device(self, serial: str, name: str = ""):
        """Add a device to track"""
        self.devices[serial] = {
            'name': name or serial,
            'json': {'status': 'pending', 'size': 0, 'start_time': None},
            'videos': {'status': 'pending', 'current': 0, 'total': 0, 'size': 0, 'start_time': None},
            'images': {'status': 'pending', 'current': 0, 'total': 0, 'size': 0, 'start_time': None}
        }
    
    def update_json_status(self, serial: str, status: str, size: int = 0):
        """Update JSON transfer status"""
        if serial in self.devices:
            self.devices[serial]['json']['status'] = status
            self.devices[serial]['json']['size'] = size
            if status == 'in_progress' and self.devices[serial]['json']['start_time'] is None:
                self.devices[serial]['json']['start_time'] = time.time()
            self._display_progress_realtime()
    
    def update_videos_progress(self, serial: str, current: int, total: int, status: str = 'in_progress'):
        """Update video transfer progress"""
        if serial in self.devices:
            self.devices[serial]['videos'].update({
                'current': current,
                'total': total,
                'status': status
            })
            if status == 'in_progress' and self.devices[serial]['videos']['start_time'] is None:
                self.devices[serial]['videos']['start_time'] = time.time()
            self._display_progress_realtime()
    
    def update_images_progress(self, serial: str, current: int, total: int, status: str = 'in_progress'):
        """Update image transfer progress"""
        if serial in self.devices:
            self.devices[serial]['images'].update({
                'current': current,
                'total': total,
                'status': status
            })
            if status == 'in_progress' and self.devices[serial]['images']['start_time'] is None:
                self.devices[serial]['images']['start_time'] = time.time()
            self._display_progress_realtime()
    
    def _display_progress_realtime(self):
        """Display transfer progress with real-time text percentages"""
        current_time = time.time()
        
        # Throttle updates to avoid excessive flickering
        if current_time - self.last_update_time < self.update_interval:
            return
        self.last_update_time = current_time
        
        # Clear screen and move cursor to top
        print("\033[2J\033[H", end="")
        
        print("=" * 60)
        print("ELDERSVR CONTENT DEPLOYMENT - REAL-TIME PROGRESS")
        print("=" * 60)
        print()
        
        for serial, device in self.devices.items():
            print(f"[{device['name']} - {serial}]")
            print("-" * 40)
            
            # JSON transfer
            json_info = device['json']
            json_status = self._get_status_text(json_info['status'])
            if json_info['status'] == 'in_progress':
                elapsed = time.time() - json_info['start_time'] if json_info['start_time'] else 0
                print(f"  JSON File:     {json_status} [{elapsed:.1f}s]")
            else:
                size_str = self._format_size(json_info['size']) if json_info['size'] > 0 else ""
                print(f"  JSON File:     {json_status} {size_str}")
            
            # Videos transfer
            videos = device['videos']
            if videos['total'] > 0:
                percent = (videos['current'] / videos['total']) * 100
                elapsed = time.time() - videos['start_time'] if videos['start_time'] else 0
                remaining = videos['total'] - videos['current']
                
                if videos['status'] == 'in_progress':
                    # Calculate transfer speed
                    if elapsed > 0 and videos['current'] > 0:
                        speed = videos['current'] / elapsed
                        eta = remaining / speed if speed > 0 else 0
                        print(f"  Video Files:   {percent:6.2f}% ({videos['current']:3d}/{videos['total']:3d}) | Elapsed: {elapsed:.1f}s | ETA: {eta:.1f}s")
                    else:
                        print(f"  Video Files:   {percent:6.2f}% ({videos['current']:3d}/{videos['total']:3d}) | Starting...")
                else:
                    status_text = self._get_status_text(videos['status'])
                    print(f"  Video Files:   {status_text} ({videos['current']}/{videos['total']})")
            else:
                print(f"  Video Files:   {self._get_status_text(videos['status'])}")
            
            # Images transfer
            images = device['images']
            if images['total'] > 0:
                percent = (images['current'] / images['total']) * 100
                elapsed = time.time() - images['start_time'] if images['start_time'] else 0
                remaining = images['total'] - images['current']
                
                if images['status'] == 'in_progress':
                    # Calculate transfer speed
                    if elapsed > 0 and images['current'] > 0:
                        speed = images['current'] / elapsed
                        eta = remaining / speed if speed > 0 else 0
                        print(f"  Image Files:   {percent:6.2f}% ({images['current']:3d}/{images['total']:3d}) | Elapsed: {elapsed:.1f}s | ETA: {eta:.1f}s")
                    else:
                        print(f"  Image Files:   {percent:6.2f}% ({images['current']:3d}/{images['total']:3d}) | Starting...")
                else:
                    status_text = self._get_status_text(images['status'])
                    print(f"  Image Files:   {status_text} ({images['current']}/{images['total']})")
            else:
                print(f"  Image Files:   {self._get_status_text(images['status'])}")
            
            print()  # Blank line between devices
        
        # Show overall progress
        self._display_overall_progress()
    
    def _display_overall_progress(self):
        """Display overall transfer progress"""
        total_files = 0
        completed_files = 0
        
        for device in self.devices.values():
            # Count JSON file
            total_files += 1
            if device['json']['status'] == 'completed':
                completed_files += 1
            
            # Count videos
            total_files += device['videos']['total']
            completed_files += device['videos']['current']
            
            # Count images
            total_files += device['images']['total']
            completed_files += device['images']['current']
        
        if total_files > 0:
            overall_percent = (completed_files / total_files) * 100
            print("=" * 60)
            print(f"OVERALL PROGRESS: {overall_percent:6.2f}% ({completed_files}/{total_files} files)")
            print("=" * 60)
    
    def _get_status_text(self, status: str) -> str:
        """Get text representation of status"""
        status_map = {
            'pending': '⏳ Pending      ',
            'in_progress': '🔄 Transferring',
            'completed': '✅ Complete    ',
            'failed': '❌ Failed      '
        }
        return status_map.get(status, '❓ Unknown     ')
    
    def _display_progress(self):
        """Legacy display method - redirect to real-time version"""
        self._display_progress_realtime()
    
    def _get_status_symbol(self, status: str) -> str:
        """Get symbol for status"""
        symbols = {
            'pending': '⏳',
            'in_progress': '🔄',
            'completed': '✅',
            'failed': '❌'
        }
        return symbols.get(status, '❓')
    
    def _create_mini_bar(self, current: int, total: int, width: int = 12) -> str:
        """Create a mini progress bar"""
        if total == 0:
            return "░" * width
        
        progress = current / total
        filled = int(width * progress)
        return "█" * filled + "░" * (width - filled)
    
    def _format_size(self, bytes_size: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"({bytes_size:.1f}{unit})"
            bytes_size /= 1024
        return f"({bytes_size:.1f}TB)"
    
    def get_summary(self) -> Dict[str, int]:
        """Get transfer summary"""
        summary = {
            'total_devices': len(self.devices),
            'completed_devices': 0,
            'failed_transfers': 0,
            'total_files': 0,
            'completed_files': 0
        }
        
        for device in self.devices.values():
            # Count completed devices
            all_completed = (
                device['json']['status'] == 'completed' and
                device['videos']['status'] in ['completed', 'pending'] and  # pending means not applicable (master)
                device['images']['status'] in ['completed', 'pending']
            )
            
            if all_completed:
                summary['completed_devices'] += 1
            
            # Count failed transfers
            if (device['json']['status'] == 'failed' or 
                device['videos']['status'] == 'failed' or 
                device['images']['status'] == 'failed'):
                summary['failed_transfers'] += 1
            
            # Count files
            summary['total_files'] += 1  # JSON file
            summary['total_files'] += device['videos']['total']
            summary['total_files'] += device['images']['total']
            
            # Count completed files
            if device['json']['status'] == 'completed':
                summary['completed_files'] += 1
            summary['completed_files'] += device['videos']['current']
            summary['completed_files'] += device['images']['current']
        
        return summary


class DownloadProgressTable:
    """Table-based progress display for parallel downloads"""
    
    def __init__(self, max_display_files: int = 20):
        self.downloads: Dict[str, Dict[str, Any]] = {}
        self.lock = Lock()
        self.start_time = time.time()
        self.last_update = 0
        self.update_interval = 0.2  # Update every 200ms
        self.max_display_files = max_display_files
        self.completed_count = 0
        self.total_count = 0
        
    def add_download(self, filename: str, file_type: str, url: str = ""):
        """Add a new download to track"""
        with self.lock:
            self.downloads[filename] = {
                'type': file_type,
                'url': url,
                'status': 'pending',
                'progress': 0.0,
                'size_downloaded': 0,
                'total_size': 0,
                'speed': 0.0,
                'start_time': None,
                'end_time': None,
                'error': None
            }
            self.total_count += 1
    
    def update_download(self, filename: str, downloaded: int, total: int, status: str = 'downloading'):
        """Update download progress"""
        with self.lock:
            if filename in self.downloads:
                download = self.downloads[filename]
                download['size_downloaded'] = downloaded
                download['total_size'] = total
                download['status'] = status
                download['progress'] = (downloaded / total * 100) if total > 0 else 0
                
                # Calculate speed
                if download['start_time'] is None and status == 'downloading':
                    download['start_time'] = time.time()
                
                if download['start_time'] and downloaded > 0:
                    elapsed = time.time() - download['start_time']
                    if elapsed > 0:
                        download['speed'] = downloaded / elapsed
                
                # Mark completion
                if status in ['completed', 'failed']:
                    download['end_time'] = time.time()
                    if status == 'completed' and downloaded == 0:
                        # For completed downloads, ensure we show 100%
                        download['progress'] = 100.0
                        if total > 0:
                            download['size_downloaded'] = total
                
                self._update_display()
    
    def mark_completed(self, filename: str, success: bool = True, error: str = None):
        """Mark a download as completed or failed"""
        with self.lock:
            if filename in self.downloads:
                download = self.downloads[filename]
                if success:
                    download['status'] = 'completed'
                    download['progress'] = 100.0
                    if download['total_size'] > 0:
                        download['size_downloaded'] = download['total_size']
                    self.completed_count += 1
                else:
                    download['status'] = 'failed'
                    download['error'] = error
                
                download['end_time'] = time.time()
                self._update_display()
    
    def _update_display(self):
        """Update the progress table display"""
        current_time = time.time()
        
        # Throttle updates
        if current_time - self.last_update < self.update_interval:
            return
        self.last_update = current_time
        
        self._render_table()
    
    def _render_table(self):
        """Render the progress table"""
        # Clear screen and move to top
        os.system('clear' if os.name == 'posix' else 'cls')
        
        print("=" * 120)
        print("ELDERSVR PARALLEL DOWNLOAD PROGRESS")
        print("=" * 120)
        
        # Overall stats
        elapsed = time.time() - self.start_time
        overall_progress = (self.completed_count / self.total_count * 100) if self.total_count > 0 else 0
        
        # Count by status
        pending = sum(1 for d in self.downloads.values() if d['status'] == 'pending')
        downloading = sum(1 for d in self.downloads.values() if d['status'] == 'downloading')
        completed = sum(1 for d in self.downloads.values() if d['status'] == 'completed')
        failed = sum(1 for d in self.downloads.values() if d['status'] == 'failed')
        
        print(f"Overall: {overall_progress:6.2f}% | Elapsed: {elapsed:6.1f}s | Total: {self.total_count} | ⏳{pending} 🔄{downloading} ✅{completed} ❌{failed}")
        print()
        
        # Table header
        header = f"{'File Name':<35} {'Type':<12} {'Status':<12} {'Progress':<12} {'Size':<12} {'Speed':<12}"
        print(header)
        print("-" * 120)
        
        # Sort downloads: downloading first, then pending, then completed/failed
        sorted_downloads = sorted(
            self.downloads.items(),
            key=lambda x: (
                0 if x[1]['status'] == 'downloading' else
                1 if x[1]['status'] == 'pending' else
                2 if x[1]['status'] == 'completed' else
                3,  # failed
                x[0]  # Then by filename
            )
        )
        
        # Display downloads (limit to max_display_files, prioritizing active ones)
        displayed = 0
        active_count = sum(1 for d in self.downloads.values() if d['status'] in ['downloading', 'pending'])
        
        for filename, download in sorted_downloads:
            if displayed >= self.max_display_files:
                remaining = len(self.downloads) - displayed
                active_remaining = sum(1 for fn, d in sorted_downloads[displayed:] if d['status'] in ['downloading', 'pending'])
                if active_remaining > 0:
                    print(f"... and {active_remaining} more active + {remaining - active_remaining} completed files")
                else:
                    print(f"... and {remaining} more completed files")
                break
            
            # Truncate long filenames
            display_name = filename[:32] + "..." if len(filename) > 35 else filename
            
            # Status with emoji
            status_display = self._get_status_display(download['status'])
            
            # Progress bar and percentage
            progress_str = self._create_progress_bar(download['progress']) + f" {download['progress']:5.1f}%"
            
            # Size information
            if download['total_size'] > 0:
                size_str = f"{self._format_size(download['size_downloaded'])}/{self._format_size(download['total_size'])}"
            elif download['size_downloaded'] > 0:
                size_str = self._format_size(download['size_downloaded'])
            else:
                size_str = "Unknown"
            
            # Speed information
            if download['speed'] > 0 and download['status'] == 'downloading':
                speed_str = f"{self._format_speed(download['speed'])}"
                
                # Add ETA if we have total size
                if download['total_size'] > 0 and download['size_downloaded'] > 0:
                    remaining_bytes = download['total_size'] - download['size_downloaded']
                    eta_seconds = remaining_bytes / download['speed']
                    speed_str += f" ETA:{eta_seconds:4.0f}s"
            elif download['status'] == 'completed':
                if download['start_time'] and download['end_time']:
                    total_time = download['end_time'] - download['start_time']
                    if total_time > 0 and download['total_size'] > 0:
                        avg_speed = download['total_size'] / total_time
                        speed_str = f"Avg: {self._format_speed(avg_speed)}"
                    else:
                        speed_str = "Done"
                else:
                    speed_str = "Done"
            elif download['status'] == 'failed':
                speed_str = "Failed"
            else:
                speed_str = "-"
            
            # Error info for failed downloads
            if download['status'] == 'failed' and download['error']:
                error_preview = download['error'][:40] + "..." if len(download['error']) > 40 else download['error']
                speed_str = f"Error: {error_preview}"
            
            print(f"{display_name:<35} {download['type']:<12} {status_display:<12} {progress_str:<12} {size_str:<12} {speed_str:<12}")
            displayed += 1
        
        print("-" * 120)
        
        # Summary stats
        total_downloaded = sum(d['size_downloaded'] for d in self.downloads.values())
        total_size = sum(d['total_size'] for d in self.downloads.values() if d['total_size'] > 0)
        
        if total_size > 0:
            overall_size_progress = (total_downloaded / total_size * 100)
            print(f"Data: {overall_size_progress:5.1f}% | Downloaded: {self._format_size(total_downloaded)} / {self._format_size(total_size)}")
        else:
            print(f"Data: Downloaded {self._format_size(total_downloaded)}")
        
        print("=" * 120)
        sys.stdout.flush()
    
    def _get_status_display(self, status: str) -> str:
        """Get display string for status"""
        status_map = {
            'pending': '⏳ Pending',
            'downloading': '🔄 Download',
            'completed': '✅ Complete',
            'failed': '❌ Failed'
        }
        return status_map.get(status, '❓ Unknown')
    
    def _create_progress_bar(self, progress: float, width: int = 8) -> str:
        """Create a mini progress bar"""
        filled = int((progress / 100) * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"
    
    def _format_size(self, bytes_size: int) -> str:
        """Format file size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:6.1f}{unit}"
            bytes_size /= 1024
        return f"{bytes_size:6.1f}TB"
    
    def _format_speed(self, bytes_per_sec: float) -> str:
        """Format download speed"""
        for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
            if bytes_per_sec < 1024:
                return f"{bytes_per_sec:5.1f}{unit}"
            bytes_per_sec /= 1024
        return f"{bytes_per_sec:5.1f}TB/s"
    
    def get_summary(self) -> Dict[str, Any]:
        """Get download summary"""
        with self.lock:
            completed = sum(1 for d in self.downloads.values() if d['status'] == 'completed')
            failed = sum(1 for d in self.downloads.values() if d['status'] == 'failed')
            downloading = sum(1 for d in self.downloads.values() if d['status'] == 'downloading')
            pending = sum(1 for d in self.downloads.values() if d['status'] == 'pending')
            
            total_downloaded = sum(d['size_downloaded'] for d in self.downloads.values())
            
            return {
                'total_files': len(self.downloads),
                'completed': completed,
                'failed': failed,
                'downloading': downloading,
                'pending': pending,
                'total_downloaded': total_downloaded,
                'elapsed_time': time.time() - self.start_time
            }
    
    def finish(self):
        """Finish the progress display"""
        # Final update with summary
        print(f"\n📊 Download Summary:")
        summary = self.get_summary()
        print(f"   Total files: {summary['total_files']}")
        print(f"   ✅ Completed: {summary['completed']}")
        print(f"   ❌ Failed: {summary['failed']}")
        print(f"   📦 Total downloaded: {self._format_size(summary['total_downloaded'])}")
        print(f"   ⏱️  Total time: {summary['elapsed_time']:.1f}s")
        
        if summary['failed'] == 0:
            print(f"\n🎉 All downloads completed successfully!")
        else:
            print(f"\n⚠️  {summary['failed']} download(s) failed.")


def print_deployment_summary(progress: TransferProgress):
    """Print final deployment summary"""
    summary = progress.get_summary()
    
    print("\n" + "="*50)
    print("DEPLOYMENT SUMMARY")
    print("="*50)
    print(f"Total devices: {summary['total_devices']}")
    print(f"Successfully completed: {summary['completed_devices']}")
    print(f"Failed transfers: {summary['failed_transfers']}")
    print(f"Files transferred: {summary['completed_files']}/{summary['total_files']}")
    
    if summary['failed_transfers'] == 0:
        print("\n✅ All transfers completed successfully!")
    else:
        print(f"\n❌ {summary['failed_transfers']} transfer(s) failed. Check logs for details.")
    
    print("="*50)