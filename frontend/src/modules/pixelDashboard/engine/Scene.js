import { CANVAS_WIDTH, CANVAS_HEIGHT } from '../constants';
import Character from './Character';
import SpriteGenerator from './SpriteGenerator';
import ArchiveZone from '../zones/ArchiveZone';
import DeskZone from '../zones/DeskZone';
import DeliveryZone from '../zones/DeliveryZone';
import ManagerRoom from '../zones/ManagerRoom';
import FactoryZone from '../zones/FactoryZone';

export default class Scene {
  constructor() {
    this.spriteGen = new SpriteGenerator();
    this.characters = [];
    this.zones = [];
    this.status = {};
  }

  init() {
    // Create character pool (3 per zone, 5 zones = 15 characters)
    for (let i = 0; i < 15; i++) {
      this.characters.push(new Character(this.spriteGen, i, 0, 100));
    }

    this.zones = [
      new ArchiveZone(this.characters.slice(0, 3)),
      new DeskZone(this.characters.slice(3, 6)),
      new DeliveryZone(this.characters.slice(6, 9)),
      new ManagerRoom(this.characters.slice(9, 12)),
      new FactoryZone(this.characters.slice(12, 15)),
    ];
  }

  setStatus(status) {
    this.status = status;
  }

  update(dt) {
    this.zones.forEach(zone => zone.update(dt, this.status));
    this.characters.forEach(char => char.update(dt));
  }

  render(ctx) {
    // Background
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

    // Floor base
    ctx.fillStyle = '#2d2d44';
    ctx.fillRect(0, CANVAS_HEIGHT - 32, CANVAS_WIDTH, 32);

    // Zone separators (subtle vertical lines)
    ctx.fillStyle = '#333355';
    [96, 192, 288, 384].forEach(x => {
      ctx.fillRect(x - 1, 0, 2, CANVAS_HEIGHT);
    });

    // Render zones
    this.zones.forEach(zone => zone.render(ctx));

    // Render characters on top
    this.characters.forEach(char => char.render(ctx));
  }
}
