"""Build the native window; retain existing project data in place."""
import argparse,plistlib,subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=root.parent/'Cutroom.app');args=p.parse_args()
app=args.output.resolve()
if app.exists():raise SystemExit(f'{app} already exists. Choose a different --output path; no existing app was overwritten.')
contents=app/'Contents';mac=contents/'MacOS';resources=contents/'Resources'
mac.mkdir(parents=True);resources.mkdir()
try:
 with tempfile.TemporaryDirectory(prefix='cutroom-desktop-') as tmp:
  cache=Path(tmp)/'module-cache';icons=Path(tmp)/'Cutroom.iconset';icons.mkdir()
  subprocess.run(['xcrun','swiftc','-O','-module-cache-path',str(cache),'-framework','AppKit','-framework','WebKit',str(root/'native/DesktopApp.swift'),'-o',str(mac/'Cutroom')],check=True)
  subprocess.run(['xcrun','swift','-module-cache-path',str(cache),str(root/'desktop/MakeIcon.swift'),str(icons)],check=True)
  subprocess.run(['/usr/bin/iconutil','-c','icns',str(icons),'-o',str(resources/'Cutroom.icns')],check=True)
 info={'CFBundleExecutable':'Cutroom','CFBundleIdentifier':'local.cutroom.desktop','CFBundleName':'Cutroom','CFBundleDisplayName':'Cutroom','CFBundlePackageType':'APPL','CFBundleVersion':'2','CFBundleShortVersionString':'2.0','CFBundleIconFile':'Cutroom.icns','NSHighResolutionCapable':True,'LSMinimumSystemVersion':'13.0','CutroomProjectRoot':str(root),'NSAppTransportSecurity':{'NSAllowsLocalNetworking':True}}
 (contents/'Info.plist').write_bytes(plistlib.dumps(info))
 subprocess.run(['/usr/bin/codesign','--force','--deep','--sign','-',str(app)],check=True)
 print(f'Built {app}\nOpen it in Finder. Closing its window leaves background video jobs running.')
except Exception:
 print(f'Build did not finish. Incomplete bundle remains at {app}; inspect it before retrying.')
 raise
