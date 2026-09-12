# Xcode handoff

The Linux VPS does not generate or sign the iOS project. On the approved Mac:

```bash
cd ~/Projects/evolve
git pull origin main
cd mobile
npm install
npx expo prebuild --platform ios
cd ios
pod install
open *.xcworkspace
```

Select a simulator, build and run, then later configure the approved Apple
Development Team, owned bundle identifier, capabilities, device, archive, and
TestFlight distribution. Never commit Apple credentials or signing material.
Universal Links require a confirmed team/bundle identifier and a future
`apple-app-site-association` deployment; neither is published yet.
