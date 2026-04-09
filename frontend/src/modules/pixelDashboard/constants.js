export const TILE_SIZE = 16;
export const CANVAS_WIDTH = 480;
export const CANVAS_HEIGHT = 160;
export const FPS = 15;
export const FRAME_DURATION = 1000 / FPS;
export const POLLING_INTERVAL = 5000;
export const CHARACTER_WIDTH = 16;
export const CHARACTER_HEIGHT = 24;

export const ZONES = {
  ARCHIVE:  { x: 0,   y: 0, width: 96,  height: 160, label: 'archive' },
  DESK:     { x: 96,  y: 0, width: 96,  height: 160, label: 'desk' },
  CORRIDOR: { x: 192, y: 0, width: 96,  height: 160, label: 'delivery' },
  MANAGER:  { x: 288, y: 0, width: 96,  height: 160, label: 'manager' },
  FACTORY:  { x: 384, y: 0, width: 96,  height: 160, label: 'factory' },
};

export const CHARACTER_STATES = {
  IDLE: 'idle',
  WALK: 'walk',
  WORK: 'work',
  RUN:  'run',
};

// Colors for placeholder characters
export const CHARACTER_COLORS = [
  '#4fc3f7', // blue
  '#81c784', // green
  '#ffb74d', // orange
  '#e57373', // red
  '#ba68c8', // purple
];
