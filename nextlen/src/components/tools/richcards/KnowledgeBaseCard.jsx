import { useEffect, useRef, useState } from 'react';
import cloud from 'd3-cloud';
import { toolsAPI } from '../../../api/tools';

const COLORS = ['#22C55E', '#a29bfe', '#fbbf24', '#00d9a3', '#8b5cf6', '#f472b6', '#38bdf8'];

const KnowledgeBaseCard = ({ clientId }) => {
  const svgRef = useRef(null);
  const [words, setWords] = useState([]);

  useEffect(() => {
    toolsAPI.getWordCloud()
      .then(res => setWords(res.data?.words || []))
      .catch(() => {});
  }, [clientId]);

  useEffect(() => {
    if (!words.length || !svgRef.current) return;

    const w = 180, h = 90;
    const maxVal = Math.max(...words.map(d => d.value));

    const layout = cloud()
      .size([w, h])
      .words(words.map(d => ({ text: d.text, size: 8 + (d.value / maxVal) * 14 })))
      .padding(1)
      .rotate(() => (Math.random() > 0.7 ? 90 : 0))
      .fontSize(d => d.size)
      .on('end', draw);

    layout.start();

    function draw(computed) {
      const svg = svgRef.current;
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      g.setAttribute('transform', `translate(${w / 2},${h / 2})`);

      computed.forEach((d, i) => {
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('transform', `translate(${d.x},${d.y}) rotate(${d.rotate})`);
        text.setAttribute('font-size', `${d.size}px`);
        text.setAttribute('font-family', "'Fira Code', monospace");
        text.setAttribute('fill', COLORS[i % COLORS.length]);
        text.setAttribute('opacity', '0.85');
        text.textContent = d.text;
        g.appendChild(text);
      });

      svg.appendChild(g);
    }
  }, [words]);

  if (!words.length) {
    return (
      <div className="w-full h-[90px] flex items-center justify-center">
        <div className="text-[9px] text-gray-500">No documents yet</div>
      </div>
    );
  }

  return (
    <svg
      ref={svgRef}
      className="w-full word-cloud-fade-in"
      viewBox="0 0 180 90"
      style={{ height: 90 }}
    />
  );
};

export default KnowledgeBaseCard;
