# 0002: Stadia Maps as Exclusive Base Map Provider and Simulation Failsafe

To provide a cohesive, zero-friction visual experience without requiring users to register for third-party API keys or endure watermarked tiles, the original Stadia Maps (`osm_bright`) is adopted as the exclusive default base map provider for the workbench. While CARTO Voyager was initially evaluated, its mandatory API key enforcement created sign-up friction and watermark clutter; in contrast, Stadia Maps natively permits zero-configuration tile access on `localhost` and `127.0.0.1`. Furthermore, map tiles remain consistent across light and dark modes without automatic swapping, Auto Navigation adheres to a simple single-trip A-to-B model, and tunnel loss during simulation safely pauses progress and freezes coordinates.

## Considered Options

1. **CARTO Voyager with client-side API key banner**: Rejected due to user friction; requiring users to register for an external key, manage storage, or display a configuration banner detracts from the seamless out-of-the-box strolling experience.
2. **OpenStreetMap / Esri multi-provider switcher**: Rejected because standard OpenStreetMap and Esri tiles possess high-saturation engineering palettes that clash with the minimalist botanical design language.
3. **Automatic dark mode tile swapping**: Rejected in favor of preserving the original Stadia Maps style consistently, altering only the outer UI cards and controls in dark mode.
4. **Stadia Maps as exclusive provider with tunnel loss freeze**: Accepted because it delivers zero-configuration, watermark-free raster tiles out-of-the-box on `localhost`, preserves clean visual simplicity, and safely freezes simulated coordinates if hardware communication drops.
