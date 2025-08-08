#!/usr/bin/env python3

"""
systemd to SysV Init Script Converter

A tool to convert systemd service files to LSB-compliant SysV init scripts.
Supports various systemd service types, dependencies, and configuration options.

Author: 0xalwayslucky (wep)
License: MIT
"""

import argparse
import configparser
import glob
import os
import re
import stat
import sys
import tempfile


class SystemdServiceConverter:
    """Converts systemd service files to SysV init scripts"""
    
    def __init__(self):
        self.config = None
        self.service_name = ""
        self.output_file = ""
        self.template_service = False
        self.instance_name = ""
        self.prefix_name = ""
        
    def find_systemd_services(self):
        """Discover all systemd service files on the system"""
        search_paths = [
            '/etc/systemd/system',
            '/lib/systemd/system',
            '/usr/lib/systemd/system',
            '/usr/local/lib/systemd/system',
            '/run/systemd/system'
        ]
        
        services = []
        for search_dir in search_paths:
            if not os.path.exists(search_dir):
                continue
                
            # Find service files in main directory
            pattern = os.path.join(search_dir, "*.service")
            services.extend(glob.glob(pattern))
            
            # Search in target subdirectories (.wants, .requires)
            for subdir_pattern in ["*.wants", "*.requires"]:
                subdirs = glob.glob(os.path.join(search_dir, subdir_pattern))
                for subdir in subdirs:
                    if os.path.isdir(subdir):
                        services.extend(glob.glob(os.path.join(subdir, "*.service")))
        
        # Filter out invalid services and remove duplicates
        valid_services = []
        seen_names = set()
        
        for service_path in services:
            if not os.path.isfile(service_path) or os.path.getsize(service_path) == 0:
                continue
                
            service_name = os.path.basename(service_path)
            
            # Prefer /etc/systemd over /lib/systemd for duplicates
            if service_name in seen_names:
                if '/etc/systemd' in service_path:
                    # Replace existing entry with /etc version
                    valid_services = [s for s in valid_services if os.path.basename(s[1]) != service_name]
                    valid_services.append((service_name, service_path))
                continue
            
            seen_names.add(service_name)
            valid_services.append((service_name, service_path))
        
        return sorted(valid_services, key=lambda x: x[0])
    
    def display_services(self):
        """Display all discovered systemd services"""
        services = self.find_systemd_services()
        
        if not services:
            print("No systemd service files found on this system.")
            return
        
        print(f"Found {len(services)} systemd service files:\n")
        print(f"{'Service Name':<40} {'Path'}")
        print("-" * 80)
        
        for service_name, service_path in services:
            print(f"{service_name:<40} {service_path}")
    
    def preprocess_service_file(self, filepath):
        """Handle duplicate keys in systemd service files by merging values"""
        with open(filepath, 'r') as file:
            lines = file.readlines()
        
        processed_lines = []
        section_data = {}
        current_section = None
        
        for line in lines:
            stripped_line = line.strip()
            
            if stripped_line.startswith('[') and stripped_line.endswith(']'):
                current_section = stripped_line
                section_data[current_section] = {}
                processed_lines.append(line)
                continue
            
            if '=' in stripped_line and current_section:
                key, value = stripped_line.split('=', 1)
                key = key.strip().lower()
                
                if key in section_data[current_section]:
                    # Merge duplicate key values
                    section_data[current_section][key] += ' ' + value.strip()
                    continue
                else:
                    section_data[current_section][key] = value.strip()
                    processed_lines.append(line)
            else:
                processed_lines.append(line)
        
        return processed_lines
    
    def replace_systemd_specifiers(self, text):
        """Replace systemd specifiers with actual values"""
        if not self.template_service:
            return text
        
        replacements = {
            '%i': self.instance_name,
            '%I': self.instance_name,
            '%p': self.prefix_name,
            '%P': self.prefix_name,
            '%f': f'/{self.instance_name}',
            '%u': self.service_name,
            '%U': self.service_name
        }
        
        result = text
        for specifier, replacement in replacements.items():
            if specifier in result:
                result = result.replace(specifier, replacement)
        
        return result
    
    def parse_service_file(self, filepath):
        """Parse systemd service file into configuration object"""
        # Handle template services
        service_basename = os.path.basename(filepath)
        self.service_name = service_basename.replace('.service', '')
        
        if '@' in self.service_name:
            self.template_service = True
            parts = self.service_name.split('@')
            self.prefix_name = parts[0]
            
            if len(parts) > 1 and parts[1]:
                self.instance_name = parts[1]
            else:
                raise ValueError("Template service requires instance name")
        
        # Preprocess file to handle duplicate keys
        processed_lines = self.preprocess_service_file(filepath)
        processed_content = ''.join(processed_lines)
        
        # Replace specifiers
        processed_content = self.replace_systemd_specifiers(processed_content)
        
        # Write to temporary file for parsing
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            temp_file.write(processed_content)
            temp_filename = temp_file.name
        
        try:
            self.config = configparser.ConfigParser(interpolation=None)
            with open(temp_filename, 'r') as temp_file:
                self.config.read_file(temp_file)
        finally:
            os.unlink(temp_filename)
        
        if not self.config.has_section("Service"):
            raise ValueError("Not a valid systemd service file: missing [Service] section")
    
    def get_config_option(self, section, option, fallback=None):
        """Safely retrieve configuration option"""
        try:
            return self.config.get(section, option, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback
    
    def get_executable_path(self):
        """Extract executable path from ExecStart"""
        exec_start = self.get_config_option("Service", "ExecStart", "")
        if not exec_start:
            return ""
        
        # Remove optional prefix (-) and extract first word
        if exec_start.startswith('-'):
            exec_start = exec_start[1:]
        
        return exec_start.split()[0]
    
    def get_full_command(self):
        """Get complete ExecStart command with arguments"""
        exec_start = self.get_config_option("Service", "ExecStart", "")
        if not exec_start:
            return ""
        
        # Remove optional prefix (-)
        if exec_start.startswith('-'):
            exec_start = exec_start[1:]
        
        return exec_start
    
    def generate_lsb_header(self):
        """Generate LSB init script header"""
        print("### BEGIN INIT INFO")
        
        # Provides
        print(f"# Provides: {self.service_name}")
        
        # Dependencies
        self._generate_dependencies()
        
        # Runlevels
        self._generate_runlevels()
        
        # Description
        description = self.get_config_option("Unit", "Description", self.service_name)
        print(f"# Short-Description: {description}")
        
        # Add extended description if available
        documentation = self.get_config_option("Unit", "Documentation")
        if documentation:
            print(f"# Documentation: {documentation}")
        
        print("### END INIT INFO")
    
    def _generate_dependencies(self):
        """Generate LSB dependency information"""
        required_deps = ["$syslog", "$local_fs"]
        should_deps = []
        
        # Check for remote filesystem requirement
        exec_path = self.get_executable_path()
        if exec_path and exec_path.startswith("/usr"):
            required_deps.append("$remote_fs")
        
        # Process After and Requires
        for option in ["After", "Requires"]:
            deps = self.get_config_option("Unit", option, "")
            if deps:
                for dep in deps.split():
                    if dep == "network.target":
                        required_deps.append("$network")
                    elif dep == "syslog.target":
                        if "$syslog" not in required_deps:
                            required_deps.append("$syslog")
                    elif dep == "remote-fs.target":
                        required_deps.append("$remote_fs")
                    elif dep == "time-sync.target":
                        required_deps.append("$time")
                    elif dep == "rpcbind.service":
                        required_deps.append("$portmap")
                    elif dep == "nss-lookup.target":
                        required_deps.append("$named")
        
        # Process Wants
        wants = self.get_config_option("Unit", "Wants", "")
        if wants:
            for want in wants.split():
                if want == "network.target":
                    should_deps.append("$network")
                elif want == "remote-fs.target":
                    should_deps.append("$remote_fs")
        
        # Output dependencies
        required_str = " ".join(set(required_deps))
        print(f"# Required-Start:\t{required_str}")
        print(f"# Required-Stop:\t{required_str}")
        
        if should_deps:
            should_str = " ".join(set(should_deps))
            print(f"# Should-Start:\t{should_str}")
    
    def _generate_runlevels(self):
        """Generate runlevel information"""
        wanted_by = self.get_config_option("Install", "WantedBy", "")
        
        if wanted_by == "multi-user.target":
            print("# Default-Start:\t2 3 4 5")
            print("# Default-Stop:\t\t0 1 6")
        elif wanted_by == "graphical.target":
            print("# Default-Start:\t2 3 4 5")
            print("# Default-Stop:\t\t0 1 6")
        elif wanted_by == "basic.target":
            print("# Default-Start:\t1")
            print("# Default-Stop:\t")
        elif wanted_by == "rescue.target":
            print("# Default-Start:\t1")
            print("# Default-Stop:\t0 2 3 4 5 6")
        else:
            print("# Default-Start:\t2 3 4 5")
            print("# Default-Stop:\t\t0 1 6")
    
    def generate_script_variables(self):
        """Generate script variables and includes"""
        print(". /lib/lsb/init-functions")
        print(f"prog={self.service_name}")
        
        # Environment file
        env_file = self.get_config_option("Service", "EnvironmentFile")
        if env_file:
            if env_file.startswith('-'):
                env_file = env_file[1:]
                print(f"if test -f {env_file}; then")
                print(f"\t. {env_file}")
                print("fi")
            else:
                print(f"if test -f {env_file}; then")
                print(f"\t. {env_file}")
                print("fi")
        
        # PID file
        pidfile = self.get_config_option("Service", "PIDFile")
        if pidfile:
            print(f"PIDFILE={pidfile}")
        else:
            print("PIDFILE=/var/run/$prog.pid")
        
        # Description
        description = self.get_config_option("Unit", "Description", self.service_name)
        print(f'DESC="{description}"')
        
        # Additional metadata
        documentation = self.get_config_option("Unit", "Documentation")
        if documentation:
            print(f'# Service documentation: {documentation}')
        
        # Direct Environment variables
        environment = self.get_config_option("Service", "Environment")
        if environment:
            # Handle multiple Environment= lines merged by preprocessor
            for env_var in environment.split():
                if '=' in env_var:
                    print(f"export {env_var}")
        
        # WorkingDirectory support
        working_dir = self.get_config_option("Service", "WorkingDirectory")
        if working_dir:
            print(f"WORKDIR={working_dir}")
        
        # User/Group support
        user = self.get_config_option("Service", "User")
        group = self.get_config_option("Service", "Group")
        if user:
            print(f"USER={user}")
        if group:
            print(f"GROUP={group}")
        
        # Timeout - handle TimeoutSec, TimeoutStartSec, TimeoutStopSec separately
        timeout_sec = self.get_config_option("Service", "TimeoutSec")
        timeout_start = self.get_config_option("Service", "TimeoutStartSec")
        timeout_stop = self.get_config_option("Service", "TimeoutStopSec")
        
        if timeout_start and timeout_start != "0":
            print(f"STARTTIMEOUT={timeout_start}")
        elif timeout_sec and timeout_sec != "0":
            print(f"STARTTIMEOUT={timeout_sec}")
        
        if timeout_stop and timeout_stop != "0":
            print(f"STOPTIMEOUT={timeout_stop}")
        elif timeout_sec and timeout_sec != "0":
            print(f"STOPTIMEOUT={timeout_sec}")
        
        # Restart behavior
        restart = self.get_config_option("Service", "Restart")
        if restart and restart != "no":
            restart_sec = self.get_config_option("Service", "RestartSec", "1")
            print(f"RESTART_MODE={restart}")
            print(f"RESTART_SEC={restart_sec}")
        
        # OOM behavior
        oom_score_adjust = self.get_config_option("Service", "OOMScoreAdjust")
        if oom_score_adjust:
            print(f"OOM_SCORE_ADJUST={oom_score_adjust}")
    
    def generate_start_function(self):
        """Generate start() function"""
        print("start() {")
        print('\tlog_daemon_msg "Starting $DESC" "$prog"')
        
        # Handle multiple condition types
        condition_path = self.get_config_option("Unit", "ConditionPathExists")
        if condition_path:
            print(f"\tif [ ! -s {condition_path} ]; then")
            print("\t\tlog_end_msg 1")
            print("\t\texit 0")
            print("\tfi")
        
        condition_path_exists_glob = self.get_config_option("Unit", "ConditionPathExistsGlob")
        if condition_path_exists_glob:
            print(f"\tif ! ls {condition_path_exists_glob} 1> /dev/null 2>&1; then")
            print("\t\tlog_end_msg 1")
            print("\t\texit 0")
            print("\tfi")
        
        condition_file_not_empty = self.get_config_option("Unit", "ConditionFileNotEmpty")
        if condition_file_not_empty:
            print(f"\tif [ ! -s {condition_file_not_empty} ]; then")
            print("\t\tlog_end_msg 1")
            print("\t\texit 0")
            print("\tfi")
        
        condition_directory_not_empty = self.get_config_option("Unit", "ConditionDirectoryNotEmpty")
        if condition_directory_not_empty:
            print(f"\tif [ ! -d {condition_directory_not_empty} ] || [ -z \"$(ls -A {condition_directory_not_empty})\" ]; then")
            print("\t\tlog_end_msg 1")
            print("\t\texit 0")
            print("\tfi")
        
        # Working directory change
        working_dir = self.get_config_option("Service", "WorkingDirectory")
        if working_dir:
            print(f"\tcd {working_dir} || {{")
            print("\t\tlog_end_msg 1")
            print("\t\texit 1")
            print("\t}")
        
        # ExecStartPre
        start_pre = self.get_config_option("Service", "ExecStartPre")
        if start_pre:
            for cmd in start_pre.split(' ; '):
                cmd = cmd.strip()
                optional = cmd.startswith('-')
                if optional:
                    cmd = cmd[1:]
                
                print(f"\tstart_daemon {cmd}")
                if not optional:
                    self._add_success_check("startpre")
        
        # ExecStart
        exec_start = self.get_config_option("Service", "ExecStart")
        if exec_start:
            service_type = self.get_config_option("Service", "Type", "simple").lower()
            
            if service_type == "oneshot":
                commands = exec_start.split(' ; ')
                for cmd in commands:
                    cmd = cmd.strip()
                    if cmd.startswith('-'):
                        cmd = cmd[1:]
                    print(f"\t{cmd}")
                self._add_success_check("start")
            
            elif service_type == "forking":
                exec_path = self.get_executable_path()
                full_cmd = self.get_full_command()
                
                pidfile_opt = ""
                if self.get_config_option("Service", "PIDFile"):
                    pidfile_opt = " -p $PIDFILE"
                
                print(f"\tstart_daemon{pidfile_opt} {full_cmd}")
                self._add_timeout_check("start")
            
            else:  # simple, exec, notify, idle
                exec_path = self.get_executable_path()
                full_cmd = self.get_full_command()
                
                # Check if command has arguments
                if full_cmd != exec_path:
                    # Has arguments - use --startas
                    args = full_cmd[len(exec_path):].strip()
                    if self.get_config_option("Service", "PIDFile"):
                        print(f"\tstart-stop-daemon --start --background --pidfile $PIDFILE --startas {exec_path} -- {args}")
                    else:
                        print(f"\tstart-stop-daemon --start --background --make-pidfile --pidfile $PIDFILE --startas {exec_path} -- {args}")
                else:
                    # No arguments - use --exec
                    if self.get_config_option("Service", "PIDFile"):
                        print(f"\tstart-stop-daemon --start --background --pidfile $PIDFILE --exec {exec_path}")
                    else:
                        print(f"\tstart-stop-daemon --start --background --make-pidfile --pidfile $PIDFILE --exec {exec_path}")
                
                if service_type != "oneshot":
                    self._add_timeout_check("start")
        
        # ExecStartPost
        start_post = self.get_config_option("Service", "ExecStartPost")
        if start_post:
            for cmd in start_post.split(' ; '):
                cmd = cmd.strip()
                optional = cmd.startswith('-')
                if optional:
                    cmd = cmd[1:]
                
                print(f"\tstart_daemon {cmd}")
                if not optional:
                    self._add_success_check("start")
        
        print("}")
        print()
    
    def generate_stop_function(self):
        """Generate stop() function"""
        print("stop() {")
        print('\tlog_daemon_msg "Stopping $DESC" "$prog"')
        
        # ExecStop
        exec_stop = self.get_config_option("Service", "ExecStop")
        if exec_stop:
            for cmd in exec_stop.split(' ; '):
                cmd = cmd.strip()
                if cmd.startswith('-'):
                    cmd = cmd[1:]
                print(f"\t{cmd}")
            self._add_timeout_check("stop")
        else:
            # Use killproc
            exec_path = self.get_executable_path()
            kill_signal = self.get_config_option("Service", "KillSignal")
            
            if self.get_config_option("Service", "PIDFile"):
                print(f"\tif [ -f $PIDFILE ]; then")
                if kill_signal:
                    print(f"\t\tkillproc -p $PIDFILE -s {kill_signal} {exec_path}")
                else:
                    print(f"\t\tkillproc -p $PIDFILE {exec_path}")
                print(f"\telse")
                if kill_signal:
                    print(f"\t\tstart-stop-daemon --stop --signal {kill_signal} --name $(basename {exec_path}) --oknodo")
                else:
                    print(f"\t\tstart-stop-daemon --stop --name $(basename {exec_path}) --oknodo")
                print(f"\tfi")
            else:
                if kill_signal:
                    print(f"\tstart-stop-daemon --stop --signal {kill_signal} --name $(basename {exec_path}) --oknodo")
                else:
                    print(f"\tstart-stop-daemon --stop --name $(basename {exec_path}) --oknodo")
            
            self._add_timeout_check("stop")
        
        # ExecStopPost
        stop_post = self.get_config_option("Service", "ExecStopPost")
        if stop_post:
            for cmd in stop_post.split(' ; '):
                cmd = cmd.strip()
                optional = cmd.startswith('-')
                if optional:
                    cmd = cmd[1:]
                    print(f"\t{cmd} || true")
                else:
                    print(f"\t{cmd}")
                    self._add_success_check("stop")
        
        print("}")
        print()
    
    def generate_status_function(self):
        """Generate status() function"""
        print("status() {")
        
        exec_path = self.get_executable_path()
        if self.get_config_option("Service", "PIDFile"):
            print(f"\tif [ -f $PIDFILE ]; then")
            print(f'\t\tstatus_of_proc -p $PIDFILE {exec_path} "$prog"')
            print("\telse")
            print(f'\t\tstatus_of_proc {exec_path} "$prog"')
            print("\tfi")
        else:
            print(f'\tstatus_of_proc {exec_path} "$prog"')
        
        print("}")
        print()
    
    def generate_reload_function(self):
        """Generate reload() function if applicable"""
        exec_reload = self.get_config_option("Service", "ExecReload")
        if not exec_reload:
            return
        
        print("reload() {")
        print('\tlog_daemon_msg "Reloading $DESC" "$prog"')
        
        for cmd in exec_reload.split(' ; '):
            cmd = cmd.strip()
            optional = cmd.startswith('-')
            if optional:
                cmd = cmd[1:]
            
            print(f"\t{cmd}")
            if not optional:
                self._add_success_check("reload")
        
        print("\texit 0")
        print("}")
        print()
    
    def generate_force_reload_function(self):
        """Generate force_reload() function"""
        print("force_reload() {")
        
        if self.get_config_option("Service", "ExecReload"):
            print("\treload")
            print("\tif [ $? -ne 0 ]; then")
            print("\t\trestart")
            print("\tfi")
        else:
            print("\tstop")
            print("\tstart")
        
        print("}")
        print()
    
    def generate_case_statement(self):
        """Generate main case statement"""
        has_reload = self.get_config_option("Service", "ExecReload") is not None
        
        print('case "$1" in')
        print('\tstart)')
        print('\t\tstart')
        print('\t\t;;')
        print('\tstop)')
        print('\t\tstop')
        print('\t\t;;')
        print('\tstatus)')
        print('\t\tstatus')
        print('\t\t;;')
        print('\tforce-reload)')
        print('\t\tforce_reload')
        print('\t\t;;')
        print('\trestart)')
        print('\t\tstop')
        print('\t\tsleep 2')
        print('\t\tstart')
        print('\t\t;;')
        
        if has_reload:
            print('\treload)')
            print('\t\treload')
            print('\t\t;;')
            usage_msg = '{start|stop|status|reload|force-reload|restart}'
        else:
            usage_msg = '{start|stop|status|force-reload|restart}'
        
        print('\t*)')
        print(f'\t\techo "Usage: $0 {usage_msg}"')
        print('\t\texit 2')
        print('esac')
    
    def _add_success_check(self, action):
        """Add success check for commands"""
        print('\tif [ $? -ne 0 ]; then')
        print('\t\tlog_end_msg 1')
        print('\t\texit 1')
        print('\tfi')
        
        if action != "startpre":
            print('\tif [ $? -eq 0 ]; then')
            print('\t\tlog_end_msg 0')
            print('\tfi')
    
    def _add_timeout_check(self, action):
        """Add timeout handling"""
        timeout_val = self.get_config_option("Service", "TimeoutSec")
        if timeout_val == "0" or not timeout_val:
            self._add_success_check(action)
            return
        
        exec_path = self.get_executable_path()
        print(f"\tTIMEOUT=${timeout_var}")
        print(f"\tTEMPPID=$(pidofproc {exec_path})")
        print("\twhile [ $TIMEOUT -gt 0 ]; do")
        
        if action == "start":
            print("\t\tif /bin/kill -0 $TEMPPID 2>/dev/null; then")
            print("\t\t\tlog_end_msg 0")
            print("\t\t\tbreak")
            print("\t\tfi")
        elif action == "stop":
            print("\t\tif ! /bin/kill -0 $TEMPPID 2>/dev/null; then")
            print("\t\t\tlog_end_msg 0")
            print("\t\t\tbreak")
            print("\t\tfi")
        
        print("\t\tsleep 1")
        print("\t\tTIMEOUT=$((TIMEOUT - 1))")
        print("\tdone")
        print()
        print("\tif [ $TIMEOUT -eq 0 ]; then")
        
        if action == "stop":
            print("\t\tkill -15 $TEMPPID 2>/dev/null")
            print("\t\tsleep 2")
            print("\t\tkill -9 $TEMPPID 2>/dev/null")
            print('\t\techo "$prog killed"')
        else:
            print("\t\tlog_end_msg 1")
            print(f"\t\techo \"Timeout error occurred trying to {action} $prog (timeout: ${timeout_var} seconds)\"")
            print("\t\texit 1")
        
        print("\tfi")
    
    def generate_init_script(self):
        """Generate complete SysV init script"""
        print("#!/bin/sh")
        self.generate_lsb_header()
        print()
        self.generate_script_variables()
        print()
        self.generate_start_function()
        self.generate_stop_function()
        self.generate_status_function()
        self.generate_reload_function()
        self.generate_force_reload_function()
        self.generate_case_statement()


def main():
    parser = argparse.ArgumentParser(
        description='Convert systemd service files to SysV init scripts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''Examples:
  %(prog)s --list
  %(prog)s /etc/systemd/system/myservice.service
  %(prog)s /etc/systemd/system/myservice.service -o /etc/init.d/myservice
  sudo %(prog)s /etc/systemd/system/myservice.service --install
        '''
    )
    
    parser.add_argument('service_file', nargs='?', 
                       help='Path to the systemd service file')
    parser.add_argument('-l', '--list', action='store_true',
                       help='List all systemd services on the system')
    parser.add_argument('-o', '--output', 
                       help='Output file path (gets execute permissions automatically)')
    parser.add_argument('-i', '--install', action='store_true',
                       help='Install the converted script to /etc/init.d/ with the service name')
    
    args = parser.parse_args()
    
    converter = SystemdServiceConverter()
    
    if args.list:
        converter.display_services()
        return
    
    if not args.service_file:
        parser.error("service_file is required unless using --list")
    
    if args.install and args.output:
        parser.error("--install and --output cannot be used together")
    
    # Validate input file
    if not os.path.isfile(args.service_file):
        print(f"Error: Service file '{args.service_file}' not found")
        sys.exit(1)
    
    try:
        converter.parse_service_file(args.service_file)
    except Exception as e:
        print(f"Error parsing service file: {e}")
        sys.exit(1)
    
    # Determine output
    if args.install:
        output_file = f"/etc/init.d/{converter.service_name}"
    else:
        output_file = args.output
    
    if output_file:
        # Write to file
        try:
            # Check permissions for /etc/init.d/
            if output_file.startswith('/etc/init.d/'):
                if not os.path.exists('/etc/init.d/'):
                    print("Error: /etc/init.d/ directory does not exist.")
                    sys.exit(1)
                
                if not os.access('/etc/init.d/', os.W_OK):
                    print("Error: Permission denied. Installing to /etc/init.d/ requires root privileges.")
                    print(f"Try: sudo python3 {' '.join(sys.argv)}")
                    sys.exit(1)
            
            # Check if file exists
            if os.path.exists(output_file):
                print(f"Warning: File {output_file} already exists and will be overwritten.")
                response = input("Continue? (y/N): ")
                if response.lower() not in ['y', 'yes']:
                    print("Operation cancelled.")
                    sys.exit(0)
            
            with open(output_file, 'w') as f:
                original_stdout = sys.stdout
                sys.stdout = f
                converter.generate_init_script()
                sys.stdout = original_stdout
            
            # Set permissions
            os.chmod(output_file, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            
            if args.install:
                try:
                    os.chown(output_file, 0, 0)
                    print(f"✓ Service '{converter.service_name}' successfully installed to {output_file}")
                    print("✓ Set proper root ownership and execute permissions")
                    print(f"✓ You can now use: service {converter.service_name} start|stop|status|restart")
                except PermissionError:
                    print(f"✓ Service '{converter.service_name}' installed to {output_file}")
                    print("⚠ Warning: Could not set root ownership. Run manually:")
                    print(f"  sudo chown root:root {output_file}")
            else:
                print(f"Init script written to {output_file} with execute permissions")
                if not output_file.startswith('/etc/init.d/'):
                    print()
                    print("⚠ IMPORTANT: To install this service, run:")
                    print(f"  sudo cp {output_file} /etc/init.d/{converter.service_name}")
                    print(f"  sudo chown root:root /etc/init.d/{converter.service_name}")
                    print(f"  sudo chmod 755 /etc/init.d/{converter.service_name}")
                    print()
                    print(f"Then you can use: service {converter.service_name} start|stop|status|restart")
        
        except PermissionError:
            print(f"Error: Permission denied writing to {output_file}")
            sys.exit(1)
        except OSError as e:
            print(f"Error writing to {output_file}: {e}")
            sys.exit(1)
    else:
        # Output to stdout
        converter.generate_init_script()


if __name__ == '__main__':
    main()