import AppKit
let folder = URL(fileURLWithPath: CommandLine.arguments[1])
for size in [16,32,128,256,512] {
    for scale in [1,2] {
        let pixels=size*scale
        let rep=NSBitmapImageRep(bitmapDataPlanes:nil,pixelsWide:pixels,pixelsHigh:pixels,bitsPerSample:8,samplesPerPixel:4,hasAlpha:true,isPlanar:false,colorSpaceName:.deviceRGB,bytesPerRow:0,bitsPerPixel:0)!
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current=NSGraphicsContext(bitmapImageRep:rep)
        let p=CGFloat(pixels)
        NSColor(srgbRed:0.224,green:0.082,blue:0.129,alpha:1).setFill()
        NSBezierPath(roundedRect:NSRect(x:p*0.06,y:p*0.06,width:p*0.88,height:p*0.88),xRadius:p*0.2,yRadius:p*0.2).fill()
        NSColor(srgbRed:0.965,green:0.914,blue:0.827,alpha:1).setFill()
        for x in [0.25,0.55] { for y in [0.25,0.55] {
            NSBezierPath(rect:NSRect(x:p*x,y:p*y,width:p*0.2,height:p*0.2)).fill()
        }}
        NSGraphicsContext.restoreGraphicsState()
        let name="icon_\(size)x\(size)"+(scale==2 ? "@2x" : "")+".png"
        try rep.representation(using:.png,properties:[:])!.write(to:folder.appendingPathComponent(name))
    }
}
