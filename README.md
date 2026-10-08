# MisakaNet

## Installing Plugins

To install a plugin, run:

```bash
./dsh/plugin/install.bash <plugin-name>
```

If the plugin requires a specific profile, you may pass it with `--profile`.
**Important:** The profile name must exist on your host. Run the following to see available profiles:

```bash
./dsh/plugin/install.bash --list
# or
ls "$DSH_HOME/profiles/"
```

Never use a profile name from documentation without verifying it exists on your machine. Using a non-existent profile (e.g., `--profile web` when your host only has `desktop`) will silently create an unloaded profile that the running host will never load, making the plugin appear installed but non-functional.

The installer will resolve the correct profile automatically and warn you if the requested profile does not exist on the current host.
