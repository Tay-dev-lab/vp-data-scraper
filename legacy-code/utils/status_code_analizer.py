#!/usr/bin/env python3
import re
import json
import os
import glob
import argparse
import sys
from collections import defaultdict
from datetime import datetime

# Add the parent directory to sys.path if running as a script
if __name__ == "__main__":
    # Get the absolute path of the script
    script_path = os.path.abspath(__file__)
    
    # Get the directory containing the script
    script_dir = os.path.dirname(script_path)
    
    # Get the parent directory of the script directory (base/base)
    base_dir = os.path.dirname(os.path.dirname(script_dir))
    
    # Add the parent directory to sys.path if it's not already there
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

def get_project_root():
    """Get the absolute path to the project root directory (base/base/)"""
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # The script is in base/base/utils/, so go up ONE level to get to base/base/
    base_base_dir = os.path.dirname(script_dir)
    
    # Print for debugging
    print(f"Script directory: {script_dir}")
    print(f"Project root: {base_base_dir}")
    
    # Verify the reports directory exists or can be created
    reports_dir = os.path.join(base_base_dir, 'reports')
    try:
        os.makedirs(reports_dir, exist_ok=True)
        print(f"Reports directory: {reports_dir} (exists or created)")
    except Exception as e:
        print(f"Error creating reports directory: {e}")
    
    return base_base_dir

def parse_logs_for_status_codes(log_file_path):
    status_codes = defaultdict(lambda: defaultdict(int))
    match_count = 0
    
    print(f"Parsing log file: {log_file_path}")
    
    try:
        with open(log_file_path, 'r') as f:
            line_count = 0
            for line in f:
                line_count += 1
                
                # Try multiple patterns to match status codes
                
                # Pattern 1: "Response 200 from domain.com ("
                match = re.search(r'Response (\d+) from ([^ ]+) \(', line)
                if match:
                    status_code = int(match.group(1))
                    domain = match.group(2)
                    status_codes[domain][status_code] += 1
                    match_count += 1
                    continue
                    
                # Pattern 2: "Crawled (200) <GET domain.com>"
                match = re.search(r'Crawled \((\d+)\).*?<\w+ (?:https?://)?([^/]+)', line)
                if match:
                    status_code = int(match.group(1))
                    domain = match.group(2)
                    status_codes[domain][status_code] += 1
                    match_count += 1
                    continue
                    
                # Pattern 3: "DEBUG    Response 200 from domain.com"
                match = re.search(r'DEBUG\s+Response (\d+) from ([^ ]+)', line)
                if match:
                    status_code = int(match.group(1))
                    domain = match.group(2)
                    status_codes[domain][status_code] += 1
                    match_count += 1
                    continue
        
        print(f"Processed {line_count} lines, found {match_count} status code matches")
        
        if match_count == 0:
            print("WARNING: No status codes found in the log file!")
            print("Sample of log file content:")
            with open(log_file_path, 'r') as f:
                print(f.read(1000))  # Print first 1000 characters
    
    except Exception as e:
        print(f"Error parsing log file: {e}")
        raise
    
    return status_codes

def generate_summary_from_logs(log_file_path, output_path=None):
    """Generate a status code summary from a log file"""
    # Get the project root directory
    project_root = get_project_root()
    
    # Use the reports directory in the project root
    reports_dir = os.path.join(project_root, 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    
    # Extract spider name from log filename
    log_filename = os.path.basename(log_file_path)
    # Typical log filename format: SPIDER_NAME_log_DATETIME.log
    spider_name = log_filename.split('_log_')[0] if '_log_' in log_filename else 'unknown'
    
    # Generate timestamp for the output file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create the output filename with the required format
    output_filename = f"planning_summary_{spider_name}_{timestamp}_status.json"
    output_path = os.path.join(reports_dir, output_filename)
    
    print(f"Will save status code report to: {output_path}")
    
    status_codes = parse_logs_for_status_codes(log_file_path)
    
    # Create summary structure
    summary = {
        'log_file': log_file_path,
        'spider_name': spider_name,
        'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'domains': [],
        'status_code_summary': {}
    }
    
    # Track overall status code counts
    overall_counts = {
        '2xx_success': 0,
        '4xx_client_errors': 0,
        '5xx_server_errors': 0,
        'specific_codes': defaultdict(int)
    }
    
    for domain, codes in status_codes.items():
        # Calculate status code categories for this domain
        domain_2xx = sum(count for status, count in codes.items() if 200 <= status < 300)
        domain_4xx = sum(count for status, count in codes.items() if 400 <= status < 500)
        domain_5xx = sum(count for status, count in codes.items() if 500 <= status < 600)
        
        # Update overall counts
        overall_counts['2xx_success'] += domain_2xx
        overall_counts['4xx_client_errors'] += domain_4xx
        overall_counts['5xx_server_errors'] += domain_5xx
        
        for status, count in codes.items():
            overall_counts['specific_codes'][str(status)] += count
        
        domain_summary = {
            'domain': domain,
            'status_codes': {
                '2xx_success': domain_2xx,
                '4xx_client_errors': domain_4xx,
                '5xx_server_errors': domain_5xx,
                'specific_codes': {
                    str(status): count for status, count in codes.items()
                }
            }
        }
        summary['domains'].append(domain_summary)
    
    # Add overall summary
    summary['status_code_summary'] = {
        '2xx_success': overall_counts['2xx_success'],
        '4xx_client_errors': overall_counts['4xx_client_errors'],
        '5xx_server_errors': overall_counts['5xx_server_errors'],
        'specific_codes': dict(overall_counts['specific_codes'])
    }
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    
    # Write to file
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=4)
    
    print(f"Status code summary written to {output_path}")
    return output_path

def process_all_logs(logs_dir=None, processed_marker='.processed', force=False):
    """Process all log files in the logs directory that haven't been processed yet"""
    # If no logs directory is specified, use the default in the project
    if logs_dir is None:
        project_root = get_project_root()
        logs_dir = os.path.join(project_root, 'logs')
    
    print(f"Looking for log files in: {logs_dir}")
    
    # Create logs directory if it doesn't exist
    os.makedirs(logs_dir, exist_ok=True)
    
    # Get all log files
    log_files = glob.glob(os.path.join(logs_dir, '*.log'))
    
    print(f"Found {len(log_files)} log files: {[os.path.basename(f) for f in log_files]}")
    
    # Track processed files
    processed_files = []
    
    if not log_files:
        print(f"No log files found in {logs_dir}. Checking if directory exists...")
        if os.path.exists(logs_dir):
            print(f"Directory exists but is empty or contains no .log files")
            # List all files in the directory for debugging
            all_files = os.listdir(logs_dir)
            print(f"Files in directory: {all_files}")
        else:
            print(f"Directory does not exist: {logs_dir}")
    
    for log_file in log_files:
        # Check if this file has already been processed
        marker_file = f"{log_file}{processed_marker}"
        
        if os.path.exists(marker_file) and not force:
            print(f"Skipping already processed file: {log_file}")
            continue
        
        try:
            # Process the log file
            output_path = generate_summary_from_logs(log_file)
            processed_files.append(output_path)
            
            # Create a marker file to indicate this log has been processed
            with open(marker_file, 'w') as f:
                f.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                
            print(f"Marked {log_file} as processed")
        except Exception as e:
            print(f"Error processing {log_file}: {e}")
            import traceback
            traceback.print_exc()
    
    return processed_files

def process_specific_log(log_file_path, force=False):
    """Process a specific log file"""
    # Check if the file exists as specified
    if not os.path.exists(log_file_path):
        # Try to find the file in the project logs directory
        project_root = get_project_root()
        project_logs_dir = os.path.join(project_root, 'logs')
        
        # Try with just the filename
        alternative_path = os.path.join(project_logs_dir, os.path.basename(log_file_path))
        
        if os.path.exists(alternative_path):
            log_file_path = alternative_path
            print(f"Found log file at: {log_file_path}")
        else:
            print(f"Error: Log file not found: {log_file_path}")
            print(f"Also checked: {alternative_path}")
            return None
    
    # Check if this file has already been processed
    marker_file = f"{log_file_path}.processed"
    
    if os.path.exists(marker_file) and not force:
        print(f"File already processed: {log_file_path}")
        print("Use --force to reprocess")
        return None
    
    try:
        # Process the log file
        output_path = generate_summary_from_logs(log_file_path)
        
        # Create a marker file to indicate this log has been processed
        with open(marker_file, 'w') as f:
            f.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
        print(f"Marked {log_file_path} as processed")
        return output_path
    except Exception as e:
        print(f"Error processing {log_file_path}: {e}")
        return None

def check_directory_permissions():
    """Check if the script has permission to write to the reports directory"""
    project_root = get_project_root()
    reports_dir = os.path.join(project_root, 'reports')
    
    try:
        # Try to create the directory if it doesn't exist
        os.makedirs(reports_dir, exist_ok=True)
        
        # Try to write a test file
        test_file = os.path.join(reports_dir, 'test_write_permission.tmp')
        with open(test_file, 'w') as f:
            f.write('test')
        
        # Clean up the test file
        os.remove(test_file)
        
        print(f"Successfully verified write permissions to {reports_dir}")
        return True
    except Exception as e:
        print(f"Error: Cannot write to reports directory {reports_dir}: {e}")
        return False

def main():
    """Main function to run the status code analyzer"""
    parser = argparse.ArgumentParser(description='Analyze HTTP status codes in Scrapy log files')
    
    # Add command line arguments
    parser.add_argument('--file', '-f', help='Process a specific log file')
    parser.add_argument('--dir', '-d', help='Directory containing log files (default: project logs directory)')
    parser.add_argument('--force', action='store_true', help='Force reprocessing of already processed files')
    parser.add_argument('--all', '-a', action='store_true', help='Process all log files in the directory')
    parser.add_argument('--latest', '-l', action='store_true', help='Process only the latest log file')
    
    args = parser.parse_args()
    
    print("Starting status code analyzer...")
    
    # Get the project root directory
    project_root = get_project_root()
    print(f"Project root: {project_root}")
    
    # Check if we can write to the reports directory
    if not check_directory_permissions():
        print("ERROR: Cannot write to reports directory. Please check permissions.")
        return
    
    # Use the logs directory in the project root if not specified
    logs_dir = args.dir if args.dir else os.path.join(project_root, 'logs')
    print(f"Logs directory: {logs_dir}")
    
    if args.file:
        # Process a specific file
        file_path = args.file
        
        # If the file doesn't exist as specified, try to find it in the project logs directory
        if not os.path.exists(file_path):
            alternative_path = os.path.join(logs_dir, os.path.basename(file_path))
            if os.path.exists(alternative_path):
                file_path = alternative_path
                print(f"Found log file at: {file_path}")
            else:
                print(f"Error: Log file not found: {file_path}")
                print(f"Also checked: {alternative_path}")
                return
        
        output_path = process_specific_log(file_path, args.force)
        if output_path:
            print(f"Successfully processed: {output_path}")
    elif args.latest:
        # Process only the latest log file
        log_files = glob.glob(os.path.join(logs_dir, '*.log'))
        if not log_files:
            print(f"No log files found in {logs_dir}")
            return
        
        # Sort by modification time (newest first)
        latest_log = max(log_files, key=os.path.getmtime)
        print(f"Processing latest log file: {latest_log}")
        
        output_path = process_specific_log(latest_log, args.force)
        if output_path:
            print(f"Successfully processed: {output_path}")
    elif args.all or not args.file:
        # Process all logs in the specified directory
        processed_files = process_all_logs(logs_dir, force=args.force)
        
        if processed_files:
            print(f"Successfully processed {len(processed_files)} log files:")
            for file in processed_files:
                print(f"  - {file}")
        else:
            print("No new log files to process.")

if __name__ == "__main__":
    main()

# Example usage
# parse_logs_for_status_codes('logs/IDOX_1_log_20250228_121816.log')