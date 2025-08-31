# Nix Usage

This project includes a Nix flake for easy package management and deployment.

## Quick Start with Nix

### Run the application directly
```bash
# Run with Nix (production with gunicorn)
nix run

# Run development server
nix run .#dev
```

### Build the package
```bash
# Build the package
nix build

# The result will be available as ./result/bin/glance-ical-events
```

### Development environment
```bash
# Enter development shell with all dependencies
nix develop

# Then run the app
python app.py
```

## NixOS Service

The flake includes a NixOS module for running this as a system service.

### Using the service

Add this flake as an input to your NixOS configuration:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    glance-ical-events.url = "github:AWildLeon/Glance-iCal-Events";
  };
  
  outputs = { self, nixpkgs, glance-ical-events }: {
    nixosConfigurations.yourhostname = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        glance-ical-events.nixosModules.default
        {
          services.glance-ical-events = {
            enable = true;
            host = "0.0.0.0";  # Bind to all interfaces
            port = 8076;
            workers = 4;
          };
          
          # Optional: Open firewall port
          networking.firewall.allowedTCPPorts = [ 8076 ];
        }
      ];
    };
  };
}
```

### Service Configuration Options

- `enable`: Enable the service (default: false)
- `package`: Package to use (default: from this flake)
- `host`: Host to bind to (default: "127.0.0.1")
- `port`: Port to bind to (default: 8076)
- `workers`: Number of Gunicorn workers (default: 4)
- `user`: User to run as (default: "glance-ical-events")
- `group`: Group to run as (default: "glance-ical-events")
- `extraArgs`: Additional Gunicorn arguments (default: [])

### Service Management

```bash
# Start the service
sudo systemctl start glance-ical-events

# Enable at boot
sudo systemctl enable glance-ical-events

# Check status
sudo systemctl status glance-ical-events

# View logs
sudo journalctl -u glance-ical-events -f
```

## Using the Overlay

You can also use the overlay to add this package to your system packages:

```nix
{
  nixpkgs.overlays = [ glance-ical-events.overlays.default ];
  
  environment.systemPackages = with pkgs; [
    glance-ical-events
  ];
}
```
