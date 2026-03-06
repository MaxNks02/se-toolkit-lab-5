import React, { useEffect, useState, useCallback } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar, Line } from 'react-chartjs-2';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend
);

// Define Types for API Responses
interface ScoreBucket {
  bucket: string;
  count: number;
}

interface TimelineEntry {
  date: string;
  submissions: number;
}

interface PassRate {
  task: string;
  avg_score: number;
  attempts: number;
}

const Dashboard: React.FC = () => {
  const [lab, setLab] = useState('lab-05'); // Default to the lab you just synced
  const [scores, setScores] = useState<ScoreBucket[]>([]);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [passRates, setPassRates] = useState<PassRate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    const apiKey = localStorage.getItem('api_key'); // Get token from localStorage

    if (!apiKey) {
      setError("API Key not found. Please log in.");
      setLoading(false);
      return;
    }

    const headers = {
      'Authorization': `Bearer ${apiKey}`,
      'Accept': 'application/json',
    };

    try {
      // Fetch from the analytics endpoints implemented in Task 2
      const [scoresRes, timelineRes, passRatesRes] = await Promise.all([
        fetch(`/api/analytics/scores?lab=${lab}`, { headers }),
        fetch(`/api/analytics/timeline?lab=${lab}`, { headers }),
        fetch(`/api/analytics/pass-rates?lab=${lab}`, { headers }),
      ]);

      if (!scoresRes.ok || !timelineRes.ok || !passRatesRes.ok) {
        throw new Error("Failed to fetch analytics data.");
      }

      setScores(await scoresRes.json());
      setTimeline(await timelineRes.json());
      setPassRates(await passRatesRes.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unknown error occurred");
    } finally {
      setLoading(false);
    }
  }, [lab]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Chart Data Configurations
  const scoreChartData = {
    labels: scores.map(s => s.bucket),
    datasets: [{
      label: 'Number of Interactions',
      data: scores.map(s => s.count),
      backgroundColor: 'rgba(54, 162, 235, 0.6)',
    }],
  };

  const timelineChartData = {
    labels: timeline.map(t => t.date),
    datasets: [{
      label: 'Daily Submissions',
      data: timeline.map(t => t.submissions),
      borderColor: 'rgba(75, 192, 192, 1)',
      tension: 0.1,
      fill: false,
    }],
  };

  if (loading) return <div className="p-8 text-center">Loading Dashboard...</div>;
  if (error) return <div className="p-8 text-center text-red-500">{error}</div>;

  return (
    <div className="p-6 space-y-8 bg-gray-50 min-h-screen">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-800">Analytics Dashboard</h1>

        {/* Lab Selector */}
        <select
          value={lab}
          onChange={(e) => setLab(e.target.value)}
          className="p-2 border rounded shadow-sm bg-white"
        >
          <option value="lab-01">Lab 01</option>
          <option value="lab-02">Lab 02</option>
          <option value="lab-03">Lab 03</option>
          <option value="lab-04">Lab 04</option>
          <option value="lab-05">Lab 05</option>
        </select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Score Distribution Bar Chart */}
        <div className="bg-white p-4 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Score Distribution</h2>
          <Bar data={scoreChartData} />
        </div>

        {/* Submission Timeline Line Chart */}
        <div className="bg-white p-4 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Submission Timeline</h2>
          <Line data={timelineChartData} />
        </div>
      </div>

      {/* Pass Rates Table */}
      <div className="bg-white p-6 rounded-lg shadow overflow-x-auto">
        <h2 className="text-xl font-semibold mb-4">Task Pass Rates</h2>
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b">
              <th className="py-2 px-4">Task Title</th>
              <th className="py-2 px-4">Avg Score</th>
              <th className="py-2 px-4">Total Attempts</th>
            </tr>
          </thead>
          <tbody>
            {passRates.map((item, idx) => (
              <tr key={idx} className="border-b hover:bg-gray-50">
                <td className="py-2 px-4">{item.task}</td>
                <td className="py-2 px-4 font-mono">{item.avg_score}%</td>
                <td className="py-2 px-4">{item.attempts}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Dashboard;