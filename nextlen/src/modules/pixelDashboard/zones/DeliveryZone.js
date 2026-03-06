import { ZONES, CHARACTER_STATES } from '../constants';

export default class DeliveryZone {
  constructor(characters) {
    this.zone = ZONES.CORRIDOR;
    this.characters = characters;
    this.runTimer = 0;
  }

  update(dt, status) {
    const count = status?.rag?.recent_responses || 0;
    this.runTimer += dt;

    this.characters.forEach((char, i) => {
      if (i < count) {
        char.visible = true;
        char.setState(CHARACTER_STATES.RUN);
        // Run back and forth across corridor
        const cycle = (this.runTimer / 2000 + i * 0.3) % 2;
        const progress = cycle < 1 ? cycle : 2 - cycle;
        char.moveTo(
          this.zone.x + 8 + progress * (this.zone.width - 24),
          this.zone.height - 40
        );
      } else {
        char.visible = false;
      }
    });
  }

  render(ctx) {
    const z = this.zone;
    // Corridor walls
    ctx.fillStyle = '#455a64';
    ctx.fillRect(z.x, 0, 4, z.height - 16);
    ctx.fillRect(z.x + z.width - 4, 0, 4, z.height - 16);
    // Floor tiles
    ctx.fillStyle = '#546e7a';
    for (let i = 0; i < 6; i++) {
      ctx.fillRect(z.x + 4, z.height - 32 + (i % 2) * 2, z.width - 8, 1);
    }
    // Arrows on floor (direction indicators)
    ctx.fillStyle = '#78909c';
    for (let i = 0; i < 3; i++) {
      const ax = z.x + 20 + i * 24;
      ctx.fillRect(ax, z.height - 24, 8, 2);
      ctx.fillRect(ax + 6, z.height - 26, 2, 2);
      ctx.fillRect(ax + 6, z.height - 22, 2, 2);
    }
    // Floor
    ctx.fillStyle = '#37474f';
    ctx.fillRect(z.x, z.height - 16, z.width, 16);
  }
}
