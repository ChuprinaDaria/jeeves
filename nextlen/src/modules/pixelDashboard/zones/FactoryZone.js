import { ZONES, CHARACTER_STATES } from '../constants';

export default class FactoryZone {
  constructor(characters) {
    this.zone = ZONES.FACTORY;
    this.characters = characters;
    this.gearAngle = 0;
    this.smokeParticles = [];
    this._lastStatus = 'healthy';
  }

  update(dt, status) {
    this._lastStatus = status?.server?.status || 'healthy';
    const running = status?.celery?.running || 0;
    const cpu = status?.server?.cpu_percent || 0;

    // Spin gears based on CPU
    this.gearAngle += (cpu / 100) * dt * 0.005;

    // Smoke particles when tasks running
    if (running > 0 && Math.random() < 0.1) {
      this.smokeParticles.push({
        x: this.zone.x + 70 + Math.random() * 10,
        y: 40,
        life: 1.0,
      });
    }
    this.smokeParticles = this.smokeParticles.filter(p => {
      p.y -= 0.3;
      p.life -= dt * 0.001;
      return p.life > 0;
    });

    // Workers near conveyor
    this.characters.forEach((char, i) => {
      if (i < running) {
        char.visible = true;
        char.setState(CHARACTER_STATES.WORK);
        char.moveTo(this.zone.x + 16 + i * 24, this.zone.height - 48);
      } else {
        char.visible = false;
      }
    });
  }

  render(ctx) {
    const z = this.zone;

    // Chimney
    ctx.fillStyle = '#616161';
    ctx.fillRect(z.x + 68, 8, 16, 36);
    ctx.fillStyle = '#757575';
    ctx.fillRect(z.x + 66, 4, 20, 6);

    // Smoke particles
    this.smokeParticles.forEach(p => {
      ctx.fillStyle = `rgba(200,200,200,${p.life * 0.6})`;
      ctx.fillRect(Math.round(p.x), Math.round(p.y), 4, 4);
    });

    // Gears
    this.drawGear(ctx, z.x + 20, 50, 14);
    this.drawGear(ctx, z.x + 48, 50, 10);

    // Conveyor belt
    ctx.fillStyle = '#424242';
    ctx.fillRect(z.x + 4, z.height - 36, z.width - 8, 6);
    // Conveyor rollers
    ctx.fillStyle = '#616161';
    const offset = (this.gearAngle * 20) % 12;
    for (let i = 0; i < 8; i++) {
      ctx.fillRect(z.x + 6 + i * 12 + offset, z.height - 35, 2, 4);
    }

    // Status light
    const lightColor = this._lastStatus === 'critical' ? '#f44336' :
                       this._lastStatus === 'warning' ? '#ff9800' : '#4caf50';
    ctx.fillStyle = '#333';
    ctx.fillRect(z.x + 4, 12, 12, 28);
    ctx.fillStyle = lightColor;
    ctx.beginPath();
    ctx.arc(z.x + 10, 24, 4, 0, Math.PI * 2);
    ctx.fill();

    // Floor
    ctx.fillStyle = '#37474f';
    ctx.fillRect(z.x, z.height - 16, z.width, 16);
  }

  drawGear(ctx, cx, cy, r) {
    ctx.fillStyle = '#9e9e9e';
    // Simple gear: circle + teeth
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();
    // Teeth
    const teeth = 6;
    for (let i = 0; i < teeth; i++) {
      const angle = this.gearAngle + (i * Math.PI * 2) / teeth;
      const tx = cx + Math.cos(angle) * (r + 2);
      const ty = cy + Math.sin(angle) * (r + 2);
      ctx.fillRect(tx - 2, ty - 2, 4, 4);
    }
    // Center hole
    ctx.fillStyle = '#616161';
    ctx.beginPath();
    ctx.arc(cx, cy, 3, 0, Math.PI * 2);
    ctx.fill();
  }
}
