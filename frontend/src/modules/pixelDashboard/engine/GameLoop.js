import { FRAME_DURATION } from '../constants';

export default class GameLoop {
  constructor(updateFn, renderFn) {
    this.update = updateFn;
    this.render = renderFn;
    this.animationId = null;
    this.lastTime = 0;
    this.accumulated = 0;
  }

  start() {
    this.lastTime = performance.now();
    this.tick(this.lastTime);
  }

  tick = (currentTime) => {
    this.animationId = requestAnimationFrame(this.tick);
    const delta = currentTime - this.lastTime;
    this.lastTime = currentTime;
    this.accumulated += delta;

    while (this.accumulated >= FRAME_DURATION) {
      this.update(FRAME_DURATION);
      this.accumulated -= FRAME_DURATION;
    }

    this.render();
  };

  stop() {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
      this.animationId = null;
    }
  }
}
