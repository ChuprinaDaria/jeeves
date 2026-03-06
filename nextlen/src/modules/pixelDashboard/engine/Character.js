import { CHARACTER_STATES, CHARACTER_HEIGHT } from '../constants';

const ANIMATION_SPEED = {
  [CHARACTER_STATES.IDLE]: 500,
  [CHARACTER_STATES.WALK]: 200,
  [CHARACTER_STATES.WORK]: 400,
  [CHARACTER_STATES.RUN]:  120,
};

export default class Character {
  constructor(spriteGen, colorIndex, x, y) {
    this.spriteGen = spriteGen;
    this.colorIndex = colorIndex;
    this.x = x;
    this.y = y;
    this.targetX = x;
    this.targetY = y;
    this.state = CHARACTER_STATES.IDLE;
    this.frameTimer = 0;
    this.currentFrame = 0;
    this.speed = 0.8;
    this.flipX = false;
    this.visible = false;
  }

  setState(newState) {
    if (this.state !== newState) {
      this.state = newState;
      this.currentFrame = 0;
      this.frameTimer = 0;
    }
  }

  moveTo(x, y) {
    this.targetX = x;
    this.targetY = y;
  }

  update(dt) {
    if (!this.visible) return;

    // Animate frames
    this.frameTimer += dt;
    const speed = ANIMATION_SPEED[this.state];
    if (this.frameTimer >= speed) {
      this.frameTimer -= speed;
      this.currentFrame = (this.currentFrame + 1) % 4;
    }

    // Move towards target
    const dx = this.targetX - this.x;
    const dy = this.targetY - this.y;
    const dist = Math.sqrt(dx * dx + dy * dy);

    if (dist > 1) {
      const moveSpeed = this.state === CHARACTER_STATES.RUN ? this.speed * 2 : this.speed;
      this.x += (dx / dist) * moveSpeed;
      this.y += (dy / dist) * moveSpeed;
      this.flipX = dx < 0;
    } else {
      this.x = this.targetX;
      this.y = this.targetY;
    }
  }

  render(ctx) {
    if (!this.visible) return;
    this.spriteGen.draw(
      ctx,
      this.colorIndex,
      this.state,
      this.currentFrame,
      Math.round(this.x),
      Math.round(this.y) - CHARACTER_HEIGHT,
      this.flipX
    );
  }
}
