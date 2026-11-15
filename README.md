# Rufus for Mac

A Rufus-style interface for creating bootable USB drives on macOS, written as a single Python file using Tkinter.

Unofficial project. It is not affiliated with Rufus or its author. It is only inspired by its interface.

Status: experimental. It writes directly to disks. Try it first with an empty USB drive, or one whose data you don't care about.

## Features

- Rufus-like interface (Drive Properties, Format Options, Status), in English and Spanish (toggle with the language button).
- Lists external disks only. Internal disks never appear.
- DD image mode: copies the image block by block to /dev/rdiskN, showing speed and remaining time. Works for hybrid ISOs (Ubuntu, Debian, Fedora, Tails, Raspberry Pi OS...) and .img files. Optional SHA-256 verification when finished.
- Windows mode: formats the drive (FAT32 or exFAT, MBR or GPT), copies the ISO contents and, if install.wim is larger than 4 GB, splits it with wimlib.
- Windows customization (optional, via autounattend.xml): remove the TPM, RAM and Secure Boot requirements, skip the Microsoft account, skip the privacy questions, create a local account with the current user's name, and use your Mac's regional settings.
- Detects automatically whether an image is a Windows ISO and picks the mode.
- Operation log (the ☰ button) and a cancel button.

## Requirements

- macOS.
- Python 3 with Tkinter. The installer from python.org is recommended, since it includes it.
- Only for Windows ISOs whose install.wim is larger than 4 GB:

    brew install wimlib

## Usage

    python3 rufuspy.py

1. Plug in the USB drive and pick it under Device.
2. Click SELECT and choose the image (.iso, .img, .raw).
3. Check the mode the program chose under Image option.
4. Click START, confirm the erase, and enter your administrator password when macOS asks for it.
5. Wait until the bar reaches 100% and shows DONE. The drive is ejected automatically.

## Building a .app

With PyInstaller, from rufuspy.py and a Rufus.png in the same folder:

    mkdir -p Rufus.iconset
    for s in 16 32 64 128 256 512; do
      sips -z $s $s Rufus.png --out Rufus.iconset/icon_${s}x${s}.png
      sips -z $((s*2)) $((s*2)) Rufus.png --out Rufus.iconset/icon_${s}x${s}@2x.png
    done
    iconutil -c icns Rufus.iconset -o Rufus.icns
    pip3 install pyinstaller
    pyinstaller --windowed --noconfirm --name Rufus --icon Rufus.icns rufuspy.py
    cp -R dist/Rufus.app /Applications/

Don't paste commands with lines starting with # into zsh: they are not treated as comments and can cause a syntax error.

## How it works

1. The window runs without privileges, validates the drive and the image, and asks for confirmation.
2. It saves the job details in a temporary folder.
3. It launches a second copy of the program with administrator privileges through the native macOS dialog (osascript). Only that copy touches the disk, and before doing so it checks again that the disk is external and that its size has not changed.
4. That copy writes its progress to a file, which the window reads several times per second. The CANCEL button creates a cancel file that the process checks while it works.

macOS tools it uses: diskutil, hdiutil, and wimlib-imagex when needed.

## Differences from Rufus

- NTFS and UEFI:NTFS: not available. macOS cannot write NTFS, so for Windows it uses FAT32 with install.wim split.
- Cluster size: not available. diskutil does not allow it.
- Bad block check: not available.
- Ubuntu persistent partition: not available.
- Windows ISO download: not available.
- Fixes for old BIOSes: not available.

Notes:

- exFAT almost never boots on UEFI. Use FAT32 to install Windows.
- The option to skip the Microsoft account (BypassNRO) does not work on the most recent Windows 11 builds. If it fails, use the local account option.

## Troubleshooting

- Tkinter is missing: install Python from python.org or run brew install python-tk.
- The USB drive doesn't show up: check List USB Hard Drives. Some USB drives are detected as fixed disks.
- The packaged app won't open: run it from Terminal to see the error:

    /Applications/Rufus.app/Contents/MacOS/Rufus

- Something failed while writing: open the log with the ☰ button and check the details.

## Warning

This program writes to and erases data on disks directly. Use it at your own risk, and always double-check the device name and size before confirming.

## License

Not chosen yet. Add a LICENSE file to the repository.
