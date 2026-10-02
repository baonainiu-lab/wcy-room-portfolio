// Local review only. This intentionally simulated model never imports startup-readiness.
export class DemoProgress {
  constructor(options = {}) { this.wait = false; this.fail = false; Object.assign(this, options); this.reset(); }
  reset() { this.progress = 0; this.phase = 'loading'; this.playing = true; }
  get ceiling() { return this.fail ? 62 : this.wait ? 78 : 100; }
  settle() {
    if (this.fail && this.progress >= 62) { this.phase = 'error'; this.playing = false; }
    else if (this.wait && this.progress >= 78) this.phase = 'waiting';
    else if (this.progress >= 100) { this.phase = 'revealing'; this.playing = false; }
    else this.phase = 'loading';
  }
  setOptions({ wait = this.wait, fail = this.fail } = {}) {
    this.wait = wait; this.fail = fail;
    if (this.phase === 'complete' || this.phase === 'revealing') return;
    const resume = this.phase === 'error' && !fail;
    this.settle();
    if (resume) this.playing = true;
  }
  scrub(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return;
    this.progress = Math.max(0, Math.min(this.ceiling, number));
    this.playing = false;
    this.settle();
  }
  advance(seconds) {
    if (!this.playing || this.phase !== 'loading' || !Number.isFinite(seconds) || seconds < 0) return;
    const speed = this.progress < 25 ? 24 : this.progress < 75 ? 21 : this.progress < 90 ? 14 : 21;
    this.progress = Math.min(this.ceiling, this.progress + Math.min(seconds, .1) * speed);
    this.settle();
  }
  complete() { if (this.phase === 'revealing' && this.progress === 100) this.phase = 'complete'; }
  snapshot() { return { progress: this.progress, phase: this.phase, playing: this.playing, wait: this.wait, fail: this.fail }; }
}
