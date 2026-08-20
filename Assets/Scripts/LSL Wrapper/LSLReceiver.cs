using UnityEngine;
using System;
using System.Collections.Generic;
using LSL;

public class LslReceiver : IDisposable
{
    // ------------ Shutdown guard ------------
    public static bool ShutdownRequested { get; set; }

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
    static void ResetStatics() => ShutdownRequested = false;

    // ------------ Data related vars ------------
    private double[] dataSamples;
    private readonly int datasetSize;
    public readonly Queue<double[]> DatasetQueue;

    // ------------ LSL related vars ------------
    private readonly string[] streamId;
    private StreamInlet inlet = null;
    private bool connected;
    private bool _disposed;

    private const double LslTimeout = 0.01; // [s]
    private const int MaxBufSize = 1;       // in number of samples

    // ------------ Connection state / issues ------------
    private enum ConnectionState
    {
        Disconnected,
        Connecting,
        Connected
    }

    private enum ConnectionIssue
    {
        None,
        NoStream,
        ChannelMismatch,
        Lost
    }

    private ConnectionState state = ConnectionState.Disconnected;
    private ConnectionIssue lastIssue = ConnectionIssue.None;

    public LslReceiver(int channelsPerSample, string streamName)
    {
        datasetSize = channelsPerSample;
        DatasetQueue = new Queue<double[]>();
        streamId = new[] { "name", streamName };
        connected = false;
    }

    private void SetState(ConnectionState newState)
    {
        if (newState == state)
            return;

        state = newState;

        switch (state)
        {
            case ConnectionState.Connecting:
                if(lastIssue != ConnectionIssue.NoStream)
                {
                    Debug.Log($"LSL: Looking for the stream '{streamId[1]}'...");
                }
                break;
            case ConnectionState.Connected:
                Debug.Log($"LSL: Connected to stream '{streamId[1]}'.");
                lastIssue = ConnectionIssue.None;
                break;
            case ConnectionState.Disconnected:
                break;
        }
    }

    private void LogIssue(ConnectionIssue issue, string message, bool isError)
    {
        if (issue == lastIssue)
            return; 

        lastIssue = issue;

        if (isError)
            Debug.LogError(message);
        else
            Debug.LogWarning(message);
    }

    private bool TryConnect()
    {
        if (_disposed || ShutdownRequested) return false;

        SetState(ConnectionState.Connecting);

        StreamInfo[] results =
            LSL.LSL.resolve_stream(streamId[0], streamId[1], 1, LslTimeout);

        if (results.Length == 0)
        {
            connected = false;
            LogIssue(
                ConnectionIssue.NoStream,
                $"LSL: No stream found matching selection params for '{streamId[1]}'... aborting.",
                isError: false
            );
            SetState(ConnectionState.Disconnected);
            return false;
        }

        if (results.Length > 1)
        {
            Debug.LogWarning("LSL: More than one stream found matching selection params. Using the first.");
        }

        inlet = new StreamInlet(results[0], MaxBufSize);
        if (results[0].channel_count() != datasetSize)
        {
            inlet.close_stream();
            inlet = null;
            connected = false;
            LogIssue(
                ConnectionIssue.ChannelMismatch,
                $"LSL: Stream '{streamId[1]}' has a different number of channels than expected " +
                $"({results[0].channel_count()} != {datasetSize}). Aborting.",
                isError: true
            );
            SetState(ConnectionState.Disconnected);
            return false;
        }

        connected = true;
        SetState(ConnectionState.Connected);
        return true;
    }

   
    public void GetSamples()
    {
        if (_disposed || ShutdownRequested) return;

        if (!connected)
        {
            connected = TryConnect();
            return;
        }

        if (inlet == null)
            return;

        try
        {
            if (dataSamples == null || dataSamples.Length != datasetSize)
                dataSamples = new double[datasetSize];

            double timestamp = inlet.pull_sample(dataSamples, LslTimeout);
            if (timestamp == 0.0d)
                return;

            DatasetQueue.Enqueue(dataSamples);
            dataSamples = null;
        }
        catch (LostException)
        {
            connected = false;
            inlet = null;
            LogIssue(
                ConnectionIssue.Lost,
                $"LSL: Stream '{streamId[1]}' lost. Reconnecting at the next call.",
                isError: true
            );
            SetState(ConnectionState.Disconnected);
        }

    }

    public void Dispose() => Close();

    public void Close()
    {
        if (_disposed) return;
        _disposed = true;
        connected = false;
        state = ConnectionState.Disconnected;
        lastIssue = ConnectionIssue.None;

        // Skip native close_stream() during shutdown — the native LSL plugin
        // may already be unloaded. The OS reclaims all resources on process exit.
        if (inlet != null && !ShutdownRequested)
        {
            try { inlet.close_stream(); }
            catch (Exception e) { Debug.LogWarning($"LSL close error: {e.Message}"); }
        }
        inlet = null;
    }

    ~LslReceiver()
    {
        // Never call native code from the finalizer thread
        inlet = null;
        _disposed = true;
    }
}
