# Procedural lo-fi bed: 76 BPM, swung hats, soft kick/snare, muffled jazzy chords, vinyl crackle.
import numpy as np, wave, struct, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else 'work/lofi.wav'  # usage: lofi.py <out.wav> [seconds]
DUR_ARG = float(sys.argv[2]) if len(sys.argv) > 2 else None
STYLE = sys.argv[3] if len(sys.argv) > 3 else 'warm'  # warm | night | bright | dusk | spooky (A harmonic minor: Am7 Fmaj7 Dm7 E7)
PRESETS = {
  'warm':   dict(bpm=76, prog=[[53,57,60,64],[52,55,59,62],[50,53,57,60],[48,52,55,59]], bass=[41,40,38,36], seed=7,  lp=1800, hat=0.18, crackle=0.35),
  'night':  dict(bpm=68, prog=[[57,60,64,67],[53,57,60,64],[48,52,55,59],[55,59,62,65]], bass=[45,41,36,43], seed=21, lp=1300, hat=0.10, crackle=0.15),
  'dusk':   dict(bpm=72, prog=[[50,53,57,60],[55,58,62,65],[48,52,55,59],[53,57,60,64]], bass=[38,43,36,41], seed=28, lp=1500, hat=0.14, crackle=0.28),
  'spooky': dict(bpm=80, prog=[[57,60,64,67],[53,57,60,64],[50,53,57,60],[52,56,59,62]], bass=[45,41,38,40], seed=31, lp=1400, hat=0.16, crackle=0.2),
  'bright': dict(bpm=84, prog=[[55,59,62,66],[57,60,64,67],[53,57,60,64],[50,53,57,60]], bass=[43,45,41,38], seed=3,  lp=2400, hat=0.22, crackle=0.25),
}
PR = PRESETS[STYLE]
SR=44100; BPM=PR['bpm']; DUR=DUR_ARG or 162.0
beat=60/BPM; n=int(SR*DUR); t=np.arange(n)/SR
rng=np.random.default_rng(PR['seed'])
out=np.zeros(n)

def env(length, a=0.005, d=0.3, floor=0.0):
    l=np.arange(length)/SR
    return np.where(l<a, l/a, np.maximum(floor, np.exp(-(l-a)/d)))

def place(sig, at):
    i=int(at*SR); j=min(n, i+len(sig))
    if i<n: out[i:j]+=sig[:j-i]

# --- drums ---
kick_len=int(0.35*SR); kl=np.arange(kick_len)/SR
kick=np.sin(2*np.pi*(55*kl+40*np.exp(-kl*18)))*env(kick_len,0.002,0.12)*0.9
snare_len=int(0.25*SR); sn=rng.normal(0,1,snare_len)
# muffle the snare
from numpy.fft import rfft, irfft
def lowpass(sig, fc):
    S=rfft(sig); f=np.fft.rfftfreq(len(sig),1/SR); S*=1/(1+(f/fc)**4); return irfft(S, len(sig))
snare=lowpass(sn,2500)*env(snare_len,0.001,0.08)*0.5+np.sin(2*np.pi*185*np.arange(snare_len)/SR)*env(snare_len,0.001,0.05)*0.3
hat_len=int(0.06*SR); hat=rng.normal(0,1,hat_len); hat=hat-lowpass(hat,6000); hat*=env(hat_len,0.001,0.02)*PR['hat']
bars=int(DUR/(4*beat))+1
for b in range(bars):
    t0=b*4*beat
    place(kick,t0); place(kick,t0+2.5*beat)
    if b%4==3: place(kick*0.7,t0+3.75*beat)
    place(snare,t0+beat); place(snare,t0+3*beat)
    for k in range(8):
        sw=0.06*beat if k%2 else 0.0   # swing on the off-beats
        g=0.6 if k%2 else 1.0
        if rng.random()<0.92: place(hat*g, t0+k*beat/2+sw)

# --- chords (Fmaj7 Em7 Dm7 Cmaj7 -> jazzy loop), 2 bars each ---
def midi(m): return 440*2**((m-69)/12)
prog=PR['prog']
chord_len=int(8*beat*SR)
for b in range(0,bars,2):
    ch=prog[(b//2)%4]; t0=b*4*beat; i=int(t0*SR); j=min(n,i+chord_len); L=j-i
    if L<=0: break
    tt=np.arange(L)/SR; sig=np.zeros(L)
    for m in ch:
        f=midi(m); det=1+rng.normal(0,0.0015)
        tri=2/np.pi*np.arcsin(np.sin(2*np.pi*f*det*tt))          # soft triangle
        tri+=0.4*np.sin(2*np.pi*f*0.5*tt)                          # sub octave
        trem=1+0.08*np.sin(2*np.pi*5.5*tt)                          # wobble
        sig+=tri*trem
    e=np.ones(L); fade=int(0.6*SR); e[:fade]=np.linspace(0,1,fade); e[-fade:]=np.linspace(1,0,fade)
    out[i:j]+=lowpass(sig*e,PR['lp'])*0.11

# --- bass ---
bass_notes=PR['bass']
for b in range(bars):
    t0=b*4*beat; m=bass_notes[(b//2)%4]
    for k,(at,ln) in enumerate([(0,1.4),(2.5,1.0)]):
        L=int(ln*beat*SR); tt=np.arange(L)/SR
        bs=np.sin(2*np.pi*midi(m)*tt)*env(L,0.01,0.5)*0.35
        place(bs,t0+at*beat)

# --- vinyl crackle & hiss ---
crackle=np.zeros(n); idx=rng.integers(0,n,int(DUR*18)); crackle[idx]=rng.normal(0,1,len(idx))
crackle=lowpass(crackle,5000)*PR['crackle']
hiss=lowpass(rng.normal(0,1,n),3000)*0.012
out+=crackle+hiss
# --- glue: gentle master lowpass, soft clip, fade in/out ---
out=lowpass(out,6000)
out=np.tanh(out*1.2)/1.2
f_in=int(1.5*SR); f_out=int(4*SR); out[:f_in]*=np.linspace(0,1,f_in); out[-f_out:]*=np.linspace(1,0,f_out)
out=out/np.max(np.abs(out))*0.8
with wave.open(OUT,'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((out*32767).astype(np.int16).tobytes())
print("ok")
