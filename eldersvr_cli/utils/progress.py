"""
Progress display utilities for EldersVR CLI
"""

import sys
import time
from typing import Optional, Dict, Any


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