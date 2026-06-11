import { useRef, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CANVAS_WIDTH, CANVAS_HEIGHT } from './constants';
import GameLoop from './engine/GameLoop';
import Scene from './engine/Scene';
import usePixelStatus from './hooks/usePixelStatus';

const PixelDashboard = ({ enabled }) => {
  const canvasRef = useRef(null);
  const sceneRef = useRef(null);
  const gameLoopRef = useRef(null);
  const { t } = useTranslation();
  const status = usePixelStatus(enabled);
  const [, setReady] = useState(false);

  useEffect(() => {
    if (!enabled) return;

    const scene = new Scene();
    scene.init();
    sceneRef.current = scene;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;

    const gameLoop = new GameLoop(
      (dt) => scene.update(dt),
      () => scene.render(ctx)
    );
    gameLoopRef.current = gameLoop;
    gameLoop.start();
    setReady(true);

    return () => {
      if (gameLoopRef.current) {
        gameLoopRef.current.stop();
      }
    };
  }, [enabled]);

  useEffect(() => {
    if (sceneRef.current && status) {
      sceneRef.current.setStatus(status);
    }
  }, [status]);

  if (!enabled) return null;

  return (
    <div className="rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 bg-gray-900">
      <div className="px-4 py-2 border-b border-gray-700 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-300">
          {t('pixelDashboard.title')}
        </span>
        {status?.server?.status && (
          <span className={`inline-block w-2 h-2 rounded-full ${
            status.server.status === 'healthy' ? 'bg-green-400' :
            status.server.status === 'warning' ? 'bg-yellow-400' : 'bg-red-400'
          }`} />
        )}
      </div>
      <canvas
        ref={canvasRef}
        width={CANVAS_WIDTH}
        height={CANVAS_HEIGHT}
        className="w-full"
        style={{ imageRendering: 'pixelated' }}
      />
    </div>
  );
};

export default PixelDashboard;
