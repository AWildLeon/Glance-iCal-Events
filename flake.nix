{
  description = "Glance iCal Events API - A Flask service for fetching and serving iCal events";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        
        # Python package derivation
        glance-ical-events = pkgs.python3Packages.buildPythonApplication {
          pname = "glance-ical-events";
          version = "1.0.0";
          
          src = ./.;
          
          format = "setuptools";
          
          nativeBuildInputs = with pkgs; [ makeWrapper ];
          
          propagatedBuildInputs = with pkgs.python3Packages; [
            flask
            pytz
            icalevents
            gunicorn
          ];
          
          # Don't check runtime dependencies strictly
          pythonRuntimeDepsCheck = false;
          
          # Post-install hook to create wrapper scripts
          postInstall = ''
            # Create bin directory if it doesn't exist
            mkdir -p $out/bin
            
            # Create production wrapper script using gunicorn
            makeWrapper ${pkgs.python3Packages.gunicorn}/bin/gunicorn $out/bin/glance-ical-events \
              --add-flags "-w 4 -b 0.0.0.0:8076 app:app" \
              --set PYTHONPATH "$out/${pkgs.python3.sitePackages}:$PYTHONPATH"
            
            # Create development wrapper script  
            makeWrapper ${pkgs.python3}/bin/python $out/bin/glance-ical-events-dev \
              --add-flags "-c \"import sys; sys.path.insert(0, '$out/${pkgs.python3.sitePackages}'); import app; app.app.run(debug=True, host='0.0.0.0', port=8076)\"" \
              --set PYTHONPATH "$out/${pkgs.python3.sitePackages}:$PYTHONPATH"
          '';
          
          # Skip tests if none exist
          doCheck = false;
          doInstallCheck = false;
          
          meta = with pkgs.lib; {
            description = "Flask API service for fetching and serving iCal events for Glance widgets";
            homepage = "https://github.com/AWildLeon/Glance-iCal-Events";
            license = licenses.mit;
            maintainers = [ ];
            platforms = platforms.all;
          };
        };
        
      in {
        packages = {
          default = glance-ical-events;
          glance-ical-events = glance-ical-events;
        };
        
        # Development shell
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python3
            python3Packages.flask
            python3Packages.pytz
            python3Packages.icalevents
            python3Packages.gunicorn
            python3Packages.pip
            python3Packages.setuptools
          ];
          
          shellHook = ''
            echo "Glance iCal Events development environment"
            echo "Run 'python app.py' to start the development server"
            echo "Run 'gunicorn -w 4 -b 0.0.0.0:8076 app:app' for production"
          '';
        };
        
        # Applications for nix run
        apps = {
          default = flake-utils.lib.mkApp {
            drv = glance-ical-events;
            name = "glance-ical-events";
          };
          
          dev = flake-utils.lib.mkApp {
            drv = glance-ical-events;
            name = "glance-ical-events-dev";
          };
        };
      }) // {
        # NixOS module and service overlay
        nixosModules.default = { config, lib, pkgs, ... }:
          with lib;
          let
            cfg = config.services.glance-ical-events;
          in {
            options.services.glance-ical-events = {
              enable = mkEnableOption "Glance iCal Events API service";
              
              package = mkOption {
                type = types.package;
                default = self.packages.${pkgs.system}.default;
                description = "The glance-ical-events package to use";
              };
              
              host = mkOption {
                type = types.str;
                default = "127.0.0.1";
                description = "Host to bind the service to";
              };
              
              port = mkOption {
                type = types.port;
                default = 8076;
                description = "Port to bind the service to";
              };
              
              workers = mkOption {
                type = types.int;
                default = 4;
                description = "Number of Gunicorn worker processes";
              };
              
              user = mkOption {
                type = types.str;
                default = "glance-ical-events";
                description = "User to run the service as";
              };
              
              group = mkOption {
                type = types.str;
                default = "glance-ical-events";
                description = "Group to run the service as";
              };
              
              extraArgs = mkOption {
                type = types.listOf types.str;
                default = [ ];
                description = "Additional arguments to pass to gunicorn";
              };
            };
            
            config = mkIf cfg.enable {
              # Create user and group
              users.users.${cfg.user} = {
                isSystemUser = true;
                group = cfg.group;
                description = "Glance iCal Events service user";
              };
              
              users.groups.${cfg.group} = { };
              
              # Systemd service
              systemd.services.glance-ical-events = {
                description = "Glance iCal Events API service";
                after = [ "network.target" ];
                wantedBy = [ "multi-user.target" ];
                
                serviceConfig = {
                  Type = "exec";
                  User = cfg.user;
                  Group = cfg.group;
                  ExecStart = "${cfg.package}/bin/glance-ical-events";
                  Restart = "always";
                  RestartSec = "10";
                  
                  # Security settings
                  NoNewPrivileges = true;
                  PrivateTmp = true;
                  ProtectSystem = "strict";
                  ProtectHome = true;
                  ProtectKernelTunables = true;
                  ProtectKernelModules = true;
                  ProtectControlGroups = true;
                  RestrictRealtime = true;
                  RestrictSUIDSGID = true;
                  RemoveIPC = true;
                  PrivateDevices = true;
                };
                
                environment = {
                  PYTHONPATH = "${cfg.package}/lib/python${pkgs.python3.pythonVersion}/site-packages/glance-ical-events";
                };
              };
              
              # Optional: Open firewall port
              # networking.firewall.allowedTCPPorts = [ cfg.port ];
            };
          };
        
        # Overlay for adding the package to nixpkgs
        overlays.default = final: prev: {
          glance-ical-events = self.packages.${final.system}.default;
        };
      };
}
