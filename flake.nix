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

        # Python package derivation (keeps args OUT of the wrapper)
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
            python-dateutil
          ];

          # No tests by default
          doCheck = false;
          doInstallCheck = false;

          # Wrapper: provide app module & PYTHONPATH, accept args from systemd.
          postInstall = ''
            mkdir -p "$out/bin"
            makeWrapper ${pkgs.python3Packages.gunicorn}/bin/gunicorn \
              "$out/bin/glance-ical-events" \
              --set PYTHONPATH "$out/${pkgs.python3.sitePackages}:$PYTHONPATH" \
              --add-flags "app:app"

            '';

          meta = with pkgs.lib; {
            description = "Flask API service for fetching and serving iCal events for Glance widgets";
            homepage = "https://github.com/AWildLeon/Glance-iCal-Events";
            license = licenses.mit;
            platforms = platforms.all;
          };
        };
      in
      {
        packages = {
          default = glance-ical-events;
          glance-ical-events = glance-ical-events;
        };

        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python3
            python3Packages.flask
            python3Packages.pytz
            python3Packages.icalevents
            python3Packages.gunicorn
            python3Packages.python-dateutil
            python3Packages.pip
            python3Packages.setuptools
          ];
          shellHook = ''
            echo "Glance iCal Events development environment"
            echo "Run: python -c 'import app; app.app.run(debug=True, host=\"0.0.0.0\", port=8076)'"
            echo "Or:  gunicorn -w 4 -b 0.0.0.0:8076 app:app"
          '';
        };

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
      }
    ) // {
      # NixOS module exporting a hardened systemd service with argv from options
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
              example = [ "--timeout" "30" "--graceful-timeout" "30" ];
              description = "Additional arguments passed to gunicorn";
            };
          };

          config = mkIf cfg.enable {
            users.groups.${cfg.group} = { };
            users.users.${cfg.user} = {
              isSystemUser = true;
              group = cfg.group;
              description = "Glance iCal Events service user";
              home = "/var/empty";
              createHome = false;
            };

            systemd.services.glance-ical-events = {
              description = "Glance iCal Events API service";
              after = [ "network-online.target" ];
              wants = [ "network-online.target" ];
              wantedBy = [ "multi-user.target" ];

              serviceConfig = {
                Type = "exec";
                User = cfg.user;
                Group = cfg.group;

                # Build a safe argv string: binary + args from options
                ExecStart = lib.escapeShellArgs (
                  [
                    "${cfg.package}/bin/glance-ical-events"
                    "--workers" (toString cfg.workers)
                    "--bind" "${cfg.host}:${toString cfg.port}"
                  ] ++ cfg.extraArgs
                );

                Restart = "always";
                RestartSec = "5s";

                # Filesystem/paths
                RuntimeDirectory = "glance-ical-events";

                # Security hardening
                NoNewPrivileges = true;
                PrivateTmp = true;
                PrivateDevices = true;
                PrivateUsers = true;
                PrivateNetwork = false; # Need network access for HTTP API and iCal fetching
                PrivateMounts = true;
                ProtectSystem = "strict";
                ProtectHome = true;
                ProtectControlGroups = true;
                ProtectKernelTunables = true;
                ProtectKernelModules = true;
                ProtectKernelLogs = true;
                ProtectProc = "invisible";
                ProcSubset = "pid";
                RestrictRealtime = true;
                RestrictSUIDSGID = true;
                LockPersonality = true;
                MemoryDenyWriteExecute = true;
                ProtectClock = true;
                ProtectHostname = true;
                
                # Detailed syscall filtering for Python/Flask/HTTP service
                SystemCallFilter = [
                  "@system-service"
                  "~@cpu-emulation"
                  "~@debug"
                  "~@keyring"
                  "~@memlock"
                  "~@module"
                  "~@mount"
                  "~@obsolete"
                  "~@privileged"
                  "~@raw-io"
                  "~@reboot"
                  "~@swap"
                  "~@resources"
                ];
                SystemCallErrorNumber = "EPERM";

                # Network and syscall tightening
                RestrictAddressFamilies = [ "AF_INET" "AF_INET6" ];
                RestrictNamespaces = true;
                SystemCallArchitectures = "native";

                # Capability drop - remove all capabilities
                CapabilityBoundingSet = [ "" ];
                AmbientCapabilities = [ "" ];

                # Additional filesystem restrictions
                ReadOnlyPaths = [ "/etc/ssl" "/etc/ca-certificates" ];
                InaccessiblePaths = [ "/boot" "/home" "/root" "/opt" "/var/lib" ];
                
                # Resource limits
                LimitNOFILE = "1024";
                LimitNPROC = "64";
                LimitCORE = "0";
                
                # Additional process restrictions
                RemoveIPC = true;
                KeyringMode = "private";
                NotifyAccess = "none";

                # Misc
                UMask = "0077";
                WorkingDirectory = "/run/glance-ical-events";
                StandardOutput = "journal";
                StandardError = "journal";
              };

              # Env kept minimal; wrapper sets PYTHONPATH already.
              environment = {
                PYTHONUNBUFFERED = "1";
              };
            };

            # Optionally open a port if binding to non-localhost:
            # networking.firewall.allowedTCPPorts = mkIf (cfg.host != "127.0.0.1") [ cfg.port ];
          };
        };

      # Overlay to expose the package as pkgs.glance-ical-events
      overlays.default = final: prev: {
        glance-ical-events = self.packages.${final.system}.default;
      };
    };
}
