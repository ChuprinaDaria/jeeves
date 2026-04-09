import { CHARACTER_WIDTH, CHARACTER_HEIGHT, CHARACTER_COLORS } from '../constants';

// Generate a simple pixel character on an offscreen canvas
// Returns an object with draw() method compatible with the rest of the engine
export default class SpriteGenerator {
  constructor() {
    this.cache = new Map();
  }

  // Generate a colored pixel character
  // characterIndex determines the color, animFrame determines the pose
  generateFrame(characterIndex, state, animFrame) {
    const key = `${characterIndex}-${state}-${animFrame}`;
    if (this.cache.has(key)) return this.cache.get(key);

    const canvas = document.createElement('canvas');
    canvas.width = CHARACTER_WIDTH;
    canvas.height = CHARACTER_HEIGHT;
    const ctx = canvas.getContext('2d');

    const color = CHARACTER_COLORS[characterIndex % CHARACTER_COLORS.length];

    this.drawCharacter(ctx, color, state, animFrame);

    this.cache.set(key, canvas);
    return canvas;
  }

  drawCharacter(ctx, color, state, frame) {
    const w = CHARACTER_WIDTH;
    const h = CHARACTER_HEIGHT;

    // Head (circle-ish)
    ctx.fillStyle = '#fdd';
    ctx.fillRect(5, 1, 6, 6);

    // Eyes
    ctx.fillStyle = '#333';
    ctx.fillRect(6, 3, 1, 1);
    ctx.fillRect(9, 3, 1, 1);

    // Body
    ctx.fillStyle = color;
    ctx.fillRect(4, 7, 8, 8);

    // Arms
    const armOffset = (state === 'work' || state === 'run') ? (frame % 2 === 0 ? -1 : 1) : 0;
    ctx.fillRect(2, 8 + armOffset, 2, 6);
    ctx.fillRect(12, 8 - armOffset, 2, 6);

    // Legs
    const legOffset = (state === 'walk' || state === 'run') ? (frame % 2 === 0 ? 1 : -1) : 0;
    ctx.fillStyle = '#555';
    ctx.fillRect(5, 15, 2, 8 + legOffset);
    ctx.fillRect(9, 15, 2, 8 - legOffset);

    // Item in hand when running (paper)
    if (state === 'run') {
      ctx.fillStyle = '#fff';
      ctx.fillRect(13, 8, 3, 4);
      // Paper lines
      ctx.fillStyle = '#aaa';
      ctx.fillRect(14, 9, 1, 1);
      ctx.fillRect(14, 11, 1, 1);
    }
  }

  draw(ctx, characterIndex, state, animFrame, x, y, flipX = false) {
    const frame = this.generateFrame(characterIndex, state, animFrame);
    if (flipX) {
      ctx.save();
      ctx.scale(-1, 1);
      ctx.drawImage(frame, -x - CHARACTER_WIDTH, y);
      ctx.restore();
    } else {
      ctx.drawImage(frame, x, y);
    }
  }
}
