// Draw the Workbench memory-chip/lens mark and optionally install a Finder icon.
// swift scripts/macos-icon.swift OUTPUT.png [LAUNCHER.command]
import AppKit
import Foundation

guard CommandLine.arguments.count == 2 || CommandLine.arguments.count == 3 else {
    fatalError("Usage: swift scripts/macos-icon.swift OUTPUT.png [LAUNCHER.command]")
}
let size = 1024
let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size,
    bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
    colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
let green = NSColor(srgbRed: 0.40, green: 0.91, blue: 0.65, alpha: 1)
let ink = NSColor(srgbRed: 0.035, green: 0.065, blue: 0.055, alpha: 1)
ink.setFill()
NSBezierPath(roundedRect: NSRect(x: 48, y: 48, width: 928, height: 928), xRadius: 200, yRadius: 200).fill()
green.withAlphaComponent(0.30).setStroke()
let edge = NSBezierPath(roundedRect: NSRect(x: 62, y: 62, width: 900, height: 900), xRadius: 190, yRadius: 190)
edge.lineWidth = 6; edge.stroke()
green.setStroke()
let chip = NSBezierPath(roundedRect: NSRect(x: 246, y: 296, width: 460, height: 460), xRadius: 42, yRadius: 42)
chip.lineWidth = 24; chip.stroke()
let pins = NSBezierPath(); pins.lineWidth = 24; pins.lineCapStyle = .round
for position in stride(from: 324, through: 624, by: 100) {
    let p = CGFloat(position)
    pins.move(to: NSPoint(x: p, y: 756)); pins.line(to: NSPoint(x: p, y: 812))
    pins.move(to: NSPoint(x: 246, y: p + 50)); pins.line(to: NSPoint(x: 190, y: p + 50))
    pins.move(to: NSPoint(x: p, y: 296)); pins.line(to: NSPoint(x: p, y: 240))
    pins.move(to: NSPoint(x: 706, y: p + 50)); pins.line(to: NSPoint(x: 762, y: p + 50))
}
pins.stroke()
green.withAlphaComponent(0.55).setFill()
for row in 0..<3 {
    for column in 0..<3 {
        NSBezierPath(roundedRect: NSRect(x: 320 + column * 110, y: 570 + row * 48,
            width: 62, height: 18), xRadius: 9, yRadius: 9).fill()
    }
}
let lens = NSBezierPath(ovalIn: NSRect(x: 420, y: 264, width: 280, height: 280))
ink.setFill(); lens.fill(); green.setStroke(); lens.lineWidth = 30; lens.stroke()
let handle = NSBezierPath(); handle.lineWidth = 56; handle.lineCapStyle = .round
handle.move(to: NSPoint(x: 664, y: 300)); handle.line(to: NSPoint(x: 806, y: 158)); handle.stroke()
let gleam = NSBezierPath(); gleam.lineWidth = 14; gleam.lineCapStyle = .round
gleam.move(to: NSPoint(x: 474, y: 414)); gleam.curve(to: NSPoint(x: 548, y: 488),
    controlPoint1: NSPoint(x: 474, y: 457), controlPoint2: NSPoint(x: 505, y: 488))
NSColor(srgbRed: 0.82, green: 0.91, blue: 0.86, alpha: 1).setStroke(); gleam.stroke()
NSGraphicsContext.restoreGraphicsState()
let data = bitmap.representation(using: .png, properties: [:])!
try data.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
if CommandLine.arguments.count == 3 {
    let launcher = CommandLine.arguments[2]
    guard FileManager.default.fileExists(atPath: launcher),
          NSWorkspace.shared.setIcon(NSImage(data: data), forFile: launcher, options: []) else {
        fatalError("Could not install the Finder icon on the existing launcher")
    }
    print("Installed Workbench Finder icon")
}
