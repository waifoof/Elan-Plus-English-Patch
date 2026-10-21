"""Where the TrueType fonts for the redrawn graphics are read from.

Order: $ELAN_FONTS, then the repository's fonts/ folder, then the system font folder. The fonts/ folder
mirrors the system layout (opentype/inter/..., truetype/crosextra/..., truetype/dejavu/...), so the
tools can name fonts as FONTS + '/opentype/inter/Inter-SemiBold.otf'.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_FONTS = os.path.join(_HERE, '..', 'fonts')

if os.environ.get('ELAN_FONTS'):
    FONTS = os.environ['ELAN_FONTS']
elif os.path.isdir(_REPO_FONTS):
    FONTS = os.path.normpath(_REPO_FONTS)
else:
    FONTS = '/usr/share/fonts'
