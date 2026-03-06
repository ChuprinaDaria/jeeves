import { ZONES, CHARACTER_STATES } from '../constants';

export default class DeskZone {
  constructor(characters) {
    this.zone = ZONES.DESK;
    this.characters = characters;
  }

  update(dt, status) {
    const count = status?.documents?.processing || 0;
    this.characters.forEach((char, i) => {
      if (i < count) {
        char.visible = true;
        char.setState(CHARACTER_STATES.WORK);
        char.moveTo(this.zone.x + 20 + i * 28, this.zone.height - 48);
      } else if (i === 0 && count === 0) {
        char.visible = true;
        char.setState(CHARACTER_STATES.IDLE);
        char.moveTo(this.zone.x + 40, this.zone.height - 40);
      } else {
        char.visible = false;
      }
    });
  }

  render(ctx) {
    const z = this.zone;
    // Desks
    for (let i = 0; i < 2; i++) {
      const dx = z.x + 12 + i * 40;
      // Desk top
      ctx.fillStyle = '#8d6e63';
      ctx.fillRect(dx, z.height - 48, 32, 4);
      // Desk legs
      ctx.fillStyle = '#6d4c41';
      ctx.fillRect(dx + 2, z.height - 44, 3, 12);
      ctx.fillRect(dx + 27, z.height - 44, 3, 12);
      // Papers on desk
      ctx.fillStyle = '#fff';
      ctx.fillRect(dx + 8, z.height - 52, 8, 5);
      ctx.fillStyle = '#bbb';
      ctx.fillRect(dx + 9, z.height - 51, 6, 1);
      ctx.fillRect(dx + 9, z.height - 49, 4, 1);
      // Lamp
      ctx.fillStyle = '#ffd54f';
      ctx.fillRect(dx + 22, z.height - 60, 6, 4);
      ctx.fillStyle = '#666';
      ctx.fillRect(dx + 24, z.height - 56, 2, 8);
    }
    // Floor
    ctx.fillStyle = '#3e2723';
    ctx.fillRect(z.x, z.height - 16, z.width, 16);
  }
}
