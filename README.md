# sysd2v - systemd to SysV Init Script Converter

A modern Python 3 tool that converts systemd service files to LSB-compliant SysV init scripts.

## Features

- **Extended Systemd Support**: Handles 40+ systemd directives including advanced features
- **Universal Compatibility**: Works with any systemd service file (simple, forking, oneshot, template services)
- **Enhanced Process Management**: User/Group ownership, WorkingDirectory, Nice levels, OOM control
- **Advanced Conditions**: 4 condition types including glob patterns and content validation
- **Environment Handling**: Direct Environment= support plus EnvironmentFile processing
- **Granular Timeouts**: Separate TimeoutStartSec/TimeoutStopSec handling
- **Restart Logic**: Configurable restart modes with RestartSec delays
- **Extended Dependencies**: Before, PartOf, Conflicts, RequiredBy support
- **LSB Compliant**: Enhanced LSB headers with documentation and extended dependencies
- **Service Discovery**: Built-in `--list` command to find all systemd services on your system
- **Easy Installation**: One-command installation with `--install` option and automatic root ownership
- **Template Services**: Full support for systemd template services (`service@instance.service`)
- **Safe Operation**: File overwrite protection, permission validation, and comprehensive error handling
- **Modern Architecture**: Clean OOP design with modular, testable components

## Quick Start

### Installation

No installation required - just download and run:

```bash
# Make executable
chmod +x sysd2v.py

# Or run with Python 3
python3 sysd2v.py --help
```

### Basic Usage

```bash
# List all systemd services on your system
python3 sysd2v.py --list

# Convert a service to stdout
python3 sysd2v.py /etc/systemd/system/myservice.service

# Convert and install in one step (recommended)
sudo python3 sysd2v.py /etc/systemd/system/myservice.service --install

# Convert to a specific file
python3 sysd2v.py /etc/systemd/system/myservice.service -o /etc/init.d/myservice
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `--list` or `-l` | List all systemd service files on the system |
| `--install` or `-i` | Install directly to `/etc/init.d/` (requires root) |
| `--output FILE` or `-o FILE` | Write to specific output file |
| `--help` | Show help and usage examples |

## Examples

### Convert a Simple Service
```bash
# Find the service first
python3 sysd2v.py --list | grep ssh
# ssh.service                              /lib/systemd/system/ssh.service

# Convert and install
sudo python3 sysd2v.py /lib/systemd/system/ssh.service --install
```

### Convert a Complex Service with Arguments
```bash
# Convert services with complex ExecStart commands
python3 sysd2v.py /etc/systemd/system/multi-user.target.wants/coolercontrold.service --install
```

### Template Services
```bash
# Handle template services (service@instance.service)
python3 sysd2v.py /etc/systemd/system/getty@tty1.service -o /etc/init.d/getty-tty1
```

### Manual Installation
```bash
# Convert to file with installation instructions
python3 sysd2v.py /path/to/service.service -o /tmp/myservice-init

# The script will provide exact installation commands:
# sudo cp /tmp/myservice-init /etc/init.d/myservice
# sudo chown root:root /etc/init.d/myservice  
# sudo chmod 755 /etc/init.d/myservice
```

## What Gets Converted

The converter handles comprehensive systemd features including advanced directives:

### **Core Service Features**
| systemd Feature | SysV Equivalent |
|----------------|-----------------|
| `ExecStart` | `start()` function with intelligent daemon handling |
| `ExecStop` | `stop()` function with `killproc` |
| `ExecReload` | `reload()` function |
| `ExecStartPre/Post` | Pre/post commands in start function |
| `ExecStopPost` | Post commands in stop function (handles optional `-` prefix) |
| `Type=simple/forking/oneshot/exec/notify/idle/dbus` | Appropriate start-stop-daemon usage |
| `PIDFile` | Proper PID file handling in all functions |
| `User/Group` | `--chuid` and `--group` options |
| `WorkingDirectory` | Directory change with error handling |
| `Nice` | Priority adjustment with `nice` command |

### **Environment & Variables**
| systemd Feature | SysV Equivalent |
|----------------|-----------------|
| `Environment` | Direct variable export |
| `EnvironmentFile` | Shell script sourcing with optional handling |
| Template specifiers (`%i`, `%p`, etc.) | Replaced with actual values |

### **Dependencies & Timing**
| systemd Feature | SysV Equivalent |
|----------------|-----------------|
| `After/Before/Requires/Wants/PartOf` | LSB `Required-Start`/`Should-Start` dependencies |
| `Conflicts` | LSB `Should-Stop` and conflict handling |
| `TimeoutSec/TimeoutStartSec/TimeoutStopSec` | Separate start/stop timeout handling |
| `WantedBy/RequiredBy=multi-user.target` | `Default-Start: 2 3 4 5` |
| `WantedBy=sysinit.target` | `Default-Start: S` |

### **Advanced Conditions**
| systemd Feature | SysV Equivalent |
|----------------|-----------------|
| `ConditionPathExists` | Pre-start path existence check |
| `ConditionPathExistsGlob` | Glob pattern existence check |
| `ConditionFileNotEmpty` | File content validation |
| `ConditionDirectoryNotEmpty` | Directory content validation |

### **Restart & Recovery**
| systemd Feature | SysV Equivalent |
|----------------|-----------------|
| `Restart=always/on-failure/on-success` | Restart mode configuration |
| `RestartSec` | Configurable restart delay |
| `OOMScoreAdjust` | Out-of-memory score adjustment |

### **Documentation & Metadata**
| systemd Feature | SysV Equivalent |
|----------------|-----------------|
| `Description` | LSB `Short-Description` |
| `Documentation` | LSB `Documentation` field and comments |

## Generated Init Script Features

The generated SysV init scripts include:

- **Enhanced LSB Header**: Complete dependencies, runlevels, documentation links
- **Extended Functions**: `start`, `stop`, `status`, `restart`, `force-reload`, `try-restart`
- **Conditional Reload**: `reload` function (if ExecReload exists)
- **Advanced Logging**: LSB functions with timeout and error details
- **Robust PID Management**: Multiple PID file strategies and process tracking
- **Comprehensive Error Handling**: Detailed exit codes and diagnostic messages
- **Signal Handling**: Respects `KillSignal` and `KillMode` settings
- **Granular Timeouts**: Separate start/stop timeout handling
- **User/Group Support**: Process ownership and permission management
- **Working Directory**: Proper directory handling and validation
- **Environment Management**: Variable exports and file sourcing
- **Condition Validation**: Multiple pre-start condition checks
- **Priority Control**: Nice level and OOM score adjustment
- **Restart Logic**: Configurable restart behavior and delays

## Supported systemd Service Types

| Type | Handling |
|------|----------|
| `simple` | Uses `start-stop-daemon --background` with User/Group support |
| `exec` | Same as simple with enhanced argument parsing |
| `forking` | Uses `start_daemon`, expects service to fork itself |
| `oneshot` | Runs commands directly without backgrounding |
| `notify` | Treated as simple (notification ignored) |
| `idle` | Treated as simple |
| `dbus` | Enhanced simple handling with D-Bus considerations |

## Enhanced Features (Beyond Standard Converters)

**sysd2v** includes advanced systemd support not found in basic converters:

- ✅ **Multiple Timeout Types**: `TimeoutStartSec` vs `TimeoutStopSec`
- ✅ **Advanced Conditions**: Glob patterns, file/directory validation  
- ✅ **User/Group Management**: Process ownership with `--chuid`/`--group`
- ✅ **Working Directory**: Proper `cd` with error handling
- ✅ **Environment Variables**: Direct `Environment=` support
- ✅ **Priority Control**: `Nice` level and `OOMScoreAdjust`
- ✅ **Restart Logic**: `Restart=` modes with `RestartSec` delays
- ✅ **Extended Dependencies**: `PartOf`, `Conflicts`, `RequiredBy`
- ✅ **Try-Restart**: systemd-style conditional restart
- ✅ **Documentation Links**: Metadata preservation in comments

## Security

The converter implements security measures for the Python script operation while ensuring 1:1 translation of service content:

- **File Overwrite Protection**: Prompts before overwriting existing files
- **No Service Content Validation**: All systemd Exec*, Description, and other values are translated exactly as-is
- **Safe File Handling**: The Python script's file operations are secured, not the service content

## Requirements

- Python 3.x
- Standard Python libraries (no external dependencies)
- Linux system with LSB init functions (`/lib/lsb/init-functions`)
- Root access for installation to `/etc/init.d/`

## Troubleshooting

### Common Issues

**Service fails to start after conversion:**
- Ensure the init script has root ownership: `sudo chown root:root /etc/init.d/servicename`
- Check that the service binary exists and is executable
- Verify dependencies are available: `service servicename status`

**Permission denied errors:**
- Use `sudo` for installing to `/etc/init.d/`
- Ensure execute permissions: `chmod +x sysd2v.py`

**Template services not working:**
- Make sure you specify the instance: `service@instance.service`
- Check that the instance name is valid for the service

### Testing Converted Services

```bash
# Check syntax
sudo /etc/init.d/myservice

# Test all functions
sudo service myservice start
sudo service myservice status  
sudo service myservice stop
sudo service myservice restart
```

## Contributing

This tool handles the most common systemd service configurations. If you encounter a service that doesn't convert properly:

1. Check that it's a valid systemd service file
2. Verify all dependencies exist on the target system
3. Test the generated script manually
4. Compare with the original systemd service behavior

## Architecture

**sysd2v** features a completely custom implementation with clean, modern Python 3 architecture:

- **Object-Oriented Design**: `SystemdServiceConverter` class encapsulates all functionality
- **Enhanced Directive Processing**: 40+ systemd directives with intelligent mapping logic
- **Advanced Condition Handling**: 4 condition types with different validation strategies
- **Process Management**: User/Group ownership, working directory, and priority control
- **Environment Processing**: Direct variable export and file sourcing capabilities
- **Modular Processing**: Separate methods for parsing, generation, and installation
- **Robust Error Handling**: Comprehensive validation and detailed diagnostic messages
- **Smart Service Discovery**: Intelligent scanning of systemd directories with duplicate handling
- **Template Service Support**: Full systemd specifier replacement and instance handling
- **Security-First**: Input validation, file overwrite protection, and safe installation

## Implementation Notes

**sysd2v.py** is a solution with:
- Modern Python 3 practices and clean code structure
- No external dependencies (uses only standard library)
- **Extended systemd feature support** (40+ directives)
- Enhanced LSB-compliant init script generation
- Production-ready error handling and comprehensive logging
- Advanced process management and environment handling
- Intelligent service type detection and optimization

## Disclaimer

⚠️ **Important**: While the converter has been tested with various service files (portmaster, coolercontrold, etc.), please test thoroughly before production use.

Furthermore, this solution was developed with the assistance of Claude Code.

**Recommended Testing Process:**
1. Convert your service: `python3 sysd2v.py --install`
2. Test all functions: `service myservice start|stop|status|restart`
3. Verify proper operation under different conditions
4. Compare behavior with the original systemd service

## License

MIT License - This is a custom implementation created specifically for the sysd2v project.