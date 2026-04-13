import React, { useState } from 'react';
import { Card, Table, Tag, Typography, Collapse, Progress, Spin, Empty, Tooltip } from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined,
  ClockCircleOutlined, DatabaseOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import client from '../api/client';
import { usePipelineStatus } from '../hooks/useAnalysisData';

const { Text } = Typography;

interface RunStep {
  id: number;
  run_id: number;
  step_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at: string | null;
  completed_at: string | null;
  duration_sec: number | null;
  rows_affected: number | null;
  detail: string | null;
}

interface Run {
  id: number;
  status: 'running' | 'completed' | 'failed' | 'pending';
  started_at: string;
  completed_at: string | null;
  current_step: string | null;
  progress: number;
  error: string | null;
  steps?: RunStep[];
}

const STATUS_TAG: Record<string, React.ReactNode> = {
  completed: <Tag icon={<CheckCircleOutlined />} color="success">完成</Tag>,
  failed:    <Tag icon={<CloseCircleOutlined />} color="error">失败</Tag>,
  running:   <Tag icon={<LoadingOutlined />} color="processing">运行中</Tag>,
  pending:   <Tag icon={<ClockCircleOutlined />} color="default">等待</Tag>,
};

const STEP_STATUS_COLOR: Record<string, string> = {
  completed: '#52c41a',
  failed: '#ff4d4f',
  running: '#1677ff',
  pending: '#d9d9d9',
};

function formatDuration(sec: number | null): string {
  if (sec == null) return '-';
  if (sec < 60) return `${sec.toFixed(1)}s`;
  return `${Math.floor(sec / 60)}m ${(sec % 60).toFixed(0)}s`;
}

function formatTime(iso: string | null): string {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function totalDuration(run: Run): string {
  if (!run.started_at) return '-';
  const end = run.completed_at ? new Date(run.completed_at) : new Date();
  const sec = (end.getTime() - new Date(run.started_at).getTime()) / 1000;
  return formatDuration(sec);
}

// ── Step list inside a run ────────────────────────────────────────────
const StepList: React.FC<{ runId: number; isRunning: boolean }> = ({ runId, isRunning }) => {
  const { data, isLoading } = useQuery<Run>({
    queryKey: ['pipeline-run-detail', runId],
    queryFn: () => client.get(`/pipeline/runs/${runId}`).then(r => r.data),
    refetchInterval: isRunning ? 3000 : false,
    staleTime: isRunning ? 0 : 5 * 60 * 1000,
  });

  if (isLoading) return <div style={{ padding: 16, textAlign: 'center' }}><Spin /></div>;
  const steps = data?.steps || [];
  if (!steps.length) return <Empty description="暂无步骤记录" style={{ padding: 16 }} />;

  return (
    <div style={{ padding: '8px 16px 16px' }}>
      {steps.map((step, idx) => (
        <div key={step.id} style={{
          display: 'flex', alignItems: 'flex-start', gap: 12,
          padding: '8px 0',
          borderBottom: idx < steps.length - 1 ? '1px solid #f0f0f0' : 'none',
        }}>
          {/* Status dot */}
          <div style={{
            width: 10, height: 10, borderRadius: '50%', marginTop: 5, flexShrink: 0,
            background: STEP_STATUS_COLOR[step.status] || '#d9d9d9',
            boxShadow: step.status === 'running' ? `0 0 0 3px ${STEP_STATUS_COLOR.running}33` : 'none',
          }} />

          {/* Step name + detail */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <Text strong style={{ fontSize: 13 }}>{step.step_name}</Text>
              {step.status === 'running' && <LoadingOutlined style={{ color: '#1677ff', fontSize: 12 }} />}
              {step.status === 'failed' && <Text type="danger" style={{ fontSize: 12 }}>失败</Text>}
            </div>
            {step.detail && (
              <Text type="secondary" style={{ fontSize: 12 }}>{step.detail}</Text>
            )}
          </div>

          {/* Metrics */}
          <div style={{ display: 'flex', gap: 16, flexShrink: 0, alignItems: 'center' }}>
            {step.rows_affected != null && (
              <Tooltip title="处理行数">
                <span style={{ fontSize: 12, color: '#666' }}>
                  <DatabaseOutlined style={{ marginRight: 4 }} />
                  {step.rows_affected.toLocaleString()}
                </span>
              </Tooltip>
            )}
            <Tooltip title="耗时">
              <span style={{ fontSize: 12, color: '#666', minWidth: 48, textAlign: 'right' }}>
                <ClockCircleOutlined style={{ marginRight: 4 }} />
                {formatDuration(step.duration_sec)}
              </span>
            </Tooltip>
          </div>
        </div>
      ))}
    </div>
  );
};

// ── Main page ─────────────────────────────────────────────────────────
const PipelineRunsPage: React.FC = () => {
  const [expandedRun, setExpandedRun] = useState<number | null>(null);
  const { data: currentStatus } = usePipelineStatus(true);

  const { data: runs = [], isLoading } = useQuery<Run[]>({
    queryKey: ['pipeline-runs'],
    queryFn: () => client.get('/pipeline/runs').then(r => r.data),
    refetchInterval: currentStatus?.status === 'running' ? 5000 : false,
    staleTime: 0,
  });

  const columns = [
    {
      title: 'Run ID',
      dataIndex: 'id',
      width: 80,
      render: (id: number) => <Text code>#{id}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (s: string) => STATUS_TAG[s] || <Tag>{s}</Tag>,
    },
    {
      title: '开始时间',
      dataIndex: 'started_at',
      width: 160,
      render: formatTime,
    },
    {
      title: '总耗时',
      width: 100,
      render: (_: unknown, run: Run) => totalDuration(run),
    },
    {
      title: '当前/最后步骤',
      dataIndex: 'current_step',
      render: (step: string | null, run: Run) => (
        <span>
          {step || '-'}
          {run.status === 'running' && (
            <Progress
              percent={Math.round((run.progress || 0) * 100)}
              size="small"
              style={{ width: 120, marginLeft: 12, display: 'inline-flex' }}
              showInfo={false}
            />
          )}
        </span>
      ),
    },
    {
      title: '错误',
      dataIndex: 'error',
      render: (err: string | null) => err
        ? <Tooltip title={err}><Text type="danger" ellipsis style={{ maxWidth: 200 }}>{err}</Text></Tooltip>
        : '-',
    },
  ];

  return (
    <div>
      {/* Current run live progress */}
      {currentStatus?.status === 'running' && (
        <Card style={{ marginBottom: 16, background: '#e6f4ff', border: '1px solid #91caff' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <LoadingOutlined style={{ color: '#1677ff', fontSize: 16 }} />
            <Text strong style={{ color: '#003eb3' }}>正在运行 Pipeline...</Text>
            <Text type="secondary" style={{ fontSize: 13 }}>{currentStatus.current_step}</Text>
          </div>
          <Progress
            percent={Math.round((currentStatus.progress || 0) * 100)}
            strokeColor="#1677ff"
            size="small"
          />
        </Card>
      )}

      <Card title="Pipeline 运行历史" style={{ marginBottom: 16 }}>
        <Table<Run>
          dataSource={runs}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          size="small"
          pagination={false}
          expandable={{
            expandedRowKeys: expandedRun != null ? [expandedRun] : [],
            onExpand: (expanded, record) => setExpandedRun(expanded ? record.id : null),
            expandedRowRender: (record) => (
              <StepList runId={record.id} isRunning={record.status === 'running'} />
            ),
          }}
        />
      </Card>
    </div>
  );
};

export default PipelineRunsPage;
