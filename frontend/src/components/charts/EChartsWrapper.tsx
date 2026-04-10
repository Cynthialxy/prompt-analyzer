import React from 'react';
import ReactECharts from 'echarts-for-react';
import { Spin, Empty } from 'antd';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface Props {
  option: Record<string, any>;
  loading?: boolean;
  empty?: boolean;
  height?: number | string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onEvents?: Record<string, (params: any) => void>;
}

const EChartsWrapper: React.FC<Props> = ({
  option,
  loading = false,
  empty = false,
  height = 400,
  onEvents,
}) => {
  if (loading) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spin />
      </div>
    );
  }

  if (empty) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Empty description="暂无数据，请先运行分析管线。" />
      </div>
    );
  }

  return (
    <ReactECharts
      option={option}
      style={{ height, width: '100%' }}
      opts={{ renderer: 'canvas' }}
      onEvents={onEvents}
    />
  );
};

export default EChartsWrapper;
