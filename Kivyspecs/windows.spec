# -*- mode: python -*-

from kivy.deps import sdl2, glew
block_cipher = None

#Change the paths below as required:
a = Analysis(['..\\Abdul Qadeer\\Documents\\critter\\critter_client.py'],
             pathex=['C:\\Users\\critter', 'C:\\Python27\\Lib\\site-packages'],
             binaries=None,
             datas=None,
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='Critter',
          debug=False,
          strip=False,
          upx=True,
          console=True )
          #Change the path below to be the directory containing all code files.
coll = COLLECT(exe, Tree('..\\Abdul Qadeer\\Documents\\critter\\'),
               a.binaries,
               a.zipfiles,
               a.datas,
			*[Tree(p) for p in (sdl2.dep_bins + glew.dep_bins)],
               strip=False,
               upx=True,
               name='Critter')

