import { useEffect, useRef, useState } from 'react';
import cloud from 'd3-cloud';
import { toolsAPI } from '../../../api/tools';

// Warm Concierge palette for the word cloud — iris/sage/amber/rose only.
const COLORS = ['#9B7ED8', '#7BC89F', '#E8A86D', '#E8729A', '#9B7ED8', '#7BC89F', '#E8A86D'];

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
        text.setAttribute('font-family', "'Ubuntu Mono', monospace");
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
        <div className="font-mono text-[9px] text-fog uppercase tracking-wide">No documents yet</div>
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
