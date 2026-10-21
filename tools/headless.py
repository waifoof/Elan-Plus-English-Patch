"""Minimal headless libretro front end for testing patched builds.

  python3 headless.py <core.so> <game.cue> <outdir> <script>

script: comma-separated steps, e.g. "600,shot,START*10,300,shot,X*5,200,shot"
  N        run N frames with no buttons
  BTN*N    hold BTN for N frames then release for N frames
           (BTN: A B X Y START SELECT UP DOWN LEFT RIGHT L R L2 R2 L3 R3 -- libretro ids,
            on PS1: B=Cross, A=Circle, Y=Square, X=Triangle)
  shot     save a PNG of the current frame
"""
import ctypes as C, os, sys
from PIL import Image

RETRO_ENV_GET_SYSTEM_DIRECTORY = 9
RETRO_ENV_SET_PIXEL_FORMAT = 10
RETRO_ENV_GET_VARIABLE = 15
RETRO_ENV_GET_VARIABLE_UPDATE = 17
RETRO_ENV_GET_SAVE_DIRECTORY = 31
RETRO_ENV_GET_LOG_INTERFACE = 27
RETRO_ENV_GET_CORE_OPTIONS_VERSION = 52

IDS = {'B': 0, 'Y': 1, 'SELECT': 2, 'START': 3, 'UP': 4, 'DOWN': 5, 'LEFT': 6, 'RIGHT': 7,
       'A': 8, 'X': 9, 'L': 10, 'R': 11, 'L2': 12, 'R2': 13, 'L3': 14, 'R3': 15}


class GameInfo(C.Structure):
    _fields_ = [('path', C.c_char_p), ('data', C.c_void_p), ('size', C.c_size_t), ('meta', C.c_char_p)]


class Variable(C.Structure):
    _fields_ = [('key', C.c_char_p), ('value', C.c_char_p)]


ENV_CB = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VIDEO_CB = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUDIO_CB = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
AUDIOB_CB = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
POLL_CB = C.CFUNCTYPE(None)
STATE_CB = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)

state = {'fmt': 0, 'frame': None, 'pressed': set()}
sysdir = C.c_char_p(os.path.abspath(os.path.dirname(__file__)).encode())
opts = {b'pcsx_rearmed_bios': b'HLE', b'pcsx_rearmed_drc': os.environ.get('DRC', 'enabled').encode()}
_keep = []


def env(cmd, data):
    if cmd in (RETRO_ENV_GET_SYSTEM_DIRECTORY, RETRO_ENV_GET_SAVE_DIRECTORY):
        C.cast(data, C.POINTER(C.c_char_p))[0] = sysdir
        return True
    if cmd == RETRO_ENV_SET_PIXEL_FORMAT:
        state['fmt'] = C.cast(data, C.POINTER(C.c_int))[0]
        return True
    if cmd == RETRO_ENV_GET_VARIABLE:
        v = C.cast(data, C.POINTER(Variable))[0]
        val = opts.get(v.key)
        if val:
            buf = C.c_char_p(val); _keep.append(buf)
            C.cast(data, C.POINTER(Variable))[0].value = buf.value
            return True
        return False
    if cmd == RETRO_ENV_GET_VARIABLE_UPDATE:
        C.cast(data, C.POINTER(C.c_bool))[0] = False
        return True
    return False


def video(data, w, h, pitch):
    if not data:
        return
    raw = C.string_at(data, pitch * h)
    if state['fmt'] == 1:      # XRGB8888
        img = Image.frombuffer('RGBX', (w, h), raw, 'raw', 'BGRX', pitch, 1).convert('RGB')
    else:                      # RGB565 / 0RGB1555 -> treat as 565
        img = Image.frombuffer('RGB', (w, h), raw, 'raw', 'BGR;16', pitch, 1)
    state['frame'] = img


def main(core, game, outdir, script):
    os.makedirs(outdir, exist_ok=True)
    lib = C.CDLL(core)
    cbs = [ENV_CB(env), VIDEO_CB(video), AUDIO_CB(lambda l, r: None),
           AUDIOB_CB(lambda d, n: n), POLL_CB(lambda: None),
           STATE_CB(lambda port, dev, idx, i: 1 if port == 0 and dev == 1 and i in state['pressed'] else 0)]
    _keep.extend(cbs)
    lib.retro_set_environment(cbs[0])
    lib.retro_set_video_refresh(cbs[1])
    lib.retro_set_audio_sample(cbs[2])
    lib.retro_set_audio_sample_batch(cbs[3])
    lib.retro_set_input_poll(cbs[4])
    lib.retro_set_input_state(cbs[5])
    lib.retro_init()
    gi = GameInfo(os.path.abspath(game).encode(), None, 0, None)
    lib.retro_load_game.restype = C.c_bool
    if not lib.retro_load_game(C.byref(gi)):
        sys.exit('load failed')
    shots = 0
    lib.retro_serialize_size.restype = C.c_size_t
    lib.retro_serialize.restype = C.c_bool
    lib.retro_unserialize.restype = C.c_bool
    for _ in range(2):          # core needs a couple of frames before states work
        lib.retro_run()
    for step in script.split(','):
        step = step.strip()
        if step.startswith('save:'):
            n = lib.retro_serialize_size()
            buf = C.create_string_buffer(n)
            ok = lib.retro_serialize(buf, C.c_size_t(n))
            open(step[5:], 'wb').write(buf.raw); print('state saved' if ok else 'state save FAILED', step[5:])
            continue
        if step.startswith('load:'):
            d = open(step[5:], 'rb').read()
            buf = C.create_string_buffer(d, len(d))
            ok = lib.retro_unserialize(buf, C.c_size_t(len(d))); print('state loaded' if ok else 'state load FAILED')
            continue
        if step.startswith('ramscan'):
            import json as _j
            lib.retro_get_memory_data.restype = C.c_void_p
            lib.retro_get_memory_size.restype = C.c_size_t
            ptr = lib.retro_get_memory_data(2); n = lib.retro_get_memory_size(2)
            ram = C.string_at(ptr, n) if ptr and n else b''
            sigs = _j.load(open(os.environ.get('SIGS', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'ram_sigs.json'))))
            found = [k for k, (a, b) in sigs.items() if bytes.fromhex(a) in ram or bytes.fromhex(b) in ram]
            print('RAMSCAN', step[8:] or shots, 'ram', n, 'found', ' '.join(sorted(found)))
            continue
        if step.startswith('vram:'):
            lib.retro_get_memory_data.restype = C.c_void_p
            lib.retro_get_memory_size.restype = C.c_size_t
            ptr = lib.retro_get_memory_data(3); n = lib.retro_get_memory_size(3)
            if ptr and n:
                open(step[5:], 'wb').write(C.string_at(ptr, n)); print('VRAM dumped', n)
            else:
                print('VRAM not exposed by core')
            continue
        if step == 'shot':
            if state['frame'] is not None:
                p = os.path.join(outdir, f'shot{shots:02d}.png')
                state['frame'].save(p); print('saved', p)
            shots += 1
        elif '*' in step:
            btn, n = step.split('*'); n = int(n)
            state['pressed'] = {IDS[btn]}
            for _ in range(n): lib.retro_run()
            state['pressed'] = set()
            for _ in range(n): lib.retro_run()
        else:
            for _ in range(int(step)): lib.retro_run()
    lib.retro_unload_game(); lib.retro_deinit()


if __name__ == '__main__':
    main(*sys.argv[1:5])
