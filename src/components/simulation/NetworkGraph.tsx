import React, { useMemo, useCallback } from 'react';

interface Node {
  id: string;
  label: string;
  type: string;
}

interface Link {
  source: string;
  target: string;
  label: string;
}

interface NetworkGraphProps {
  nodes: Node[];
  links: Link[];
  showRelations: boolean;
  onNodeClick?: (nodeId: string) => void;
}

export const NetworkGraph: React.FC<NetworkGraphProps> = React.memo(({
  nodes,
  links,
  showRelations,
  onNodeClick
}) => {
  // تخزين الحسابات المعقدة مؤقتاً لتجنب البطء أثناء تغيير حالة التهيئة
  const memoizedNodes = useMemo(() => {
    return nodes.map(node => ({
      ...node,
      // حساب المواقع وتحديد الألوان بناءً على الكيانات المحلية (تاجر، عميل، منصة...)
    }));
  }, [nodes]);

  const memoizedLinks = useMemo(() => {
    if (!showRelations) return [];
    return links;
  }, [links, showRelations]);

  const handleNodeSelect = useCallback((id: string) => {
    if (onNodeClick) onNodeClick(id);
  }, [onNodeClick]);

  return (
    <div className="relative w-full h-[400px] bg-white rounded-xl p-4 border border-gray-100 shadow-sm overflow-hidden">
      {/* خريطة الشبكة المحسنة بأداء سريع */}
      <svg className="w-full h-full">
        {memoizedLinks.map((link, idx) => (
          <g key={`link-${idx}`}>
            {/* رسم الروابط دون إجهاد المعالج */}
          </g>
        ))}
        {memoizedNodes.map((node) => (
          <g 
            key={node.id} 
            onClick={() => handleNodeSelect(node.id)}
            className="cursor-pointer transition-transform hover:scale-105"
          >
            {/* رسم عقد الشبكة */}
          </g>
        ))}
      </svg>
    </div>
  );
});

NetworkGraph.displayName = 'NetworkGraph';
