import React from 'react';
import { Card, Statistic } from 'antd';

interface Props {
  title: string;
  value: number | string;
  prefix?: React.ReactNode;
  suffix?: string;
  precision?: number;
  loading?: boolean;
}

const KpiCard: React.FC<Props> = ({ title, value, prefix, suffix, precision, loading }) => (
  <Card bordered={false} style={{ borderRadius: 8 }}>
    <Statistic
      title={title}
      value={value}
      prefix={prefix}
      suffix={suffix}
      precision={precision}
      loading={loading}
    />
  </Card>
);

export default KpiCard;
