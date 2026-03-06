import { ZONES, CHARACTER_STATES } from '../constants';

export default class ManagerRoom {
  constructor(characters) {
    this.zone = ZONES.MANAGER;
    this.characters = characters;
  }

  update(dt, status) {
    const count = status?.escalations?.active || 0;
    this.characters.forEach((char, i) => {
      if (i < count) {
        char.visible = true;
        char.setState(CHARACTER_STATES.RUN);
        char.moveTo(this.zone.x + 40, this.zone.height - 56);
      } else {
        char.visible = false;
      }
    });
  }

  render(ctx) {
    const z = this.zone;
    // Door frame
    ctx.fillStyle = '#5d4037';
    ctx.fillRect(z.x + 24, 20, 48, 72);
    // Door
    ctx.fillStyle = '#795548';
    ctx.fillRect(z.x + 28, 24, 40, 64);
    // Door handle
    ctx.fillStyle = '#ffd54f';
    ctx.fillRect(z.x + 60, 52, 3, 6);
    // Sign "MGR"
    ctx.fillStyle = '#fff';
    ctx.fillRect(z.x + 36, 30, 24, 12);
    ctx.fillStyle = '#333';
    ctx.font = '8px monospace';
    ctx.fillText('MGR', z.x + 38, 39);
    // Desk behind door (visible through opening)
    ctx.fillStyle = '#6d4c41';
    ctx.fillRect(z.x + 32, 72, 32, 4);
    // Manager chair
    ctx.fillStyle = '#333';
    ctx.fillRect(z.x + 42, 64, 12, 8);
    ctx.fillRect(z.x + 44, 56, 8, 8);
    // Floor
    ctx.fillStyle = '#3e2723';
    ctx.fillRect(z.x, z.height - 16, z.width, 16);
  }
}
