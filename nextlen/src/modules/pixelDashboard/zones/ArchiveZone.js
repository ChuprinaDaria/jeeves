import { ZONES, CHARACTER_STATES } from '../constants';

export default class ArchiveZone {
  constructor(characters) {
    this.zone = ZONES.ARCHIVE;
    this.characters = characters;
  }

  update(dt, status) {
    const count = status?.rag?.active_queries || 0;
    this.characters.forEach((char, i) => {
      if (i < count) {
        char.visible = true;
        char.setState(CHARACTER_STATES.WORK);
        char.moveTo(this.zone.x + 16 + i * 24, this.zone.height - 40);
      } else if (i === 0 && count === 0) {
        // Idle character when nothing happening
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
    // Bookshelves
    for (let i = 0; i < 3; i++) {
      const sx = z.x + 8 + i * 28;
      // Shelf frame
      ctx.fillStyle = '#5b3a29';
      ctx.fillRect(sx, 16, 24, 56);
      // Books on shelves
      const bookColors = ['#c62828', '#1565c0', '#2e7d32', '#f9a825', '#6a1b9a'];
      for (let row = 0; row < 4; row++) {
        for (let b = 0; b < 3; b++) {
          ctx.fillStyle = bookColors[(i + row + b) % bookColors.length];
          ctx.fillRect(sx + 2 + b * 7, 18 + row * 13, 6, 11);
        }
      }
      // Shelf dividers
      ctx.fillStyle = '#795548';
      for (let row = 0; row < 3; row++) {
        ctx.fillRect(sx, 29 + row * 13, 24, 2);
      }
    }
    // Zone label area (floor)
    ctx.fillStyle = '#3e2723';
    ctx.fillRect(z.x, z.height - 16, z.width, 16);
  }
}
