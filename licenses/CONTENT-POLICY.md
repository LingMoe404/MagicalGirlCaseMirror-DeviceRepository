# Device Resource Content Policy

This repository may publish three first-party declarative resource types:

- device Profile resources (`.mgdevice.json`) containing exact Host Driver references, stable USB identity, dimensions, and verification metadata;
- RGB model resources (`.mgmodel.json`) containing self-authored coordinates and LED index mappings;
- Canvas resources (`.mgcanvas.json`) containing Canvas geometry, `all-compatible` targets, and Host-supported built-in effect kinds and parameters.

A new declarative Canvas resource does not require a software update. An effect kind unknown to the Host does require a Host software update before the resource can be supported.

Resources must not contain HTML, JavaScript, WebAssembly, scripts, protocol fields, device paths, vendor templates, third-party assets, binaries, SDKs, installers, or private diagnostics.

A resource contributor must provide:

- resource author or publisher;
- source and attribution information;
- applicable license or redistribution permission;
- confirmation that the submitted device Profile, RGB model, or Canvas contains no third-party binaries, SDKs, installers, private diagnostics, or unreviewed protocol implementations.

The repository does not grant permission to redistribute vendor software or SignalRGB/WhirlwindFX content. Such material must not be copied here without a separate legal review and explicit redistribution rights.
