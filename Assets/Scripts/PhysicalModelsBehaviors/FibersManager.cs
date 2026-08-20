using UnityEngine;
using System.Linq;
using System.Collections.Generic;

public class FibersManager : MonoBehaviour {
    [SerializeField] private string fiberNamePrefix = "CurveObject";
    [SerializeField] private Material fiberMaterial;
    [SerializeField] private TextAsset fibersLinesIndicesAsset;
    [SerializeField, Range(0f, 1f)] private float activationDensity = 0.01f; // percentage of fibers to activate

    private double[] values;
    private LslReceiver receiver;
    private readonly List<FiberBehavior> fiberObjects = new();
    private HashSet<int> selectedFiberIds = new();
    private HashSet<int> oldSelectedFiberIds = new();


    private void Start ()
    {
        ParseAndAddFibersAsset();
        string streamName = GameManager.instance.fiberStreamName;
        receiver = new LslReceiver(fiberObjects.Count, streamName);
    }
	
    private void Update ()
    {
        if (receiver == null) return;

        receiver.GetSamples();

        // keep track of the previously activated fibers 
        (oldSelectedFiberIds, selectedFiberIds) = (selectedFiberIds, oldSelectedFiberIds);
        selectedFiberIds.Clear();

        // check if new activity data available
        if (receiver.DatasetQueue.Count <= 0) return;
        try
        {
            values = receiver.DatasetQueue.Dequeue();
        }
        catch (System.InvalidOperationException e)
        {
            // there was no sample waiting in the queue, we can reuse the last one
            Debug.Log(e.ToString());

            // if there is none, we don't post anything
            if (values == null)
                return;
        }

        // activate the chosen percentage of fibers with the highest activation values
        var nFibersToSelect = Mathf.RoundToInt(activationDensity * values.Length);
        var data = values.Select((val, index) => new { Val = val, FiberId = index });
        var orderedValues = data.OrderByDescending(el => el.Val);
        var selectedFibers = orderedValues.Take(nFibersToSelect);

            
        foreach (var i in selectedFibers)
        {
            int idx = i.FiberId;
            selectedFiberIds.Add(idx);
            fiberObjects[idx].ActivateFiber();
        }

        // deactivate previously activated fibers that are no longer selected
        foreach (int i in oldSelectedFiberIds)
        {
            if (selectedFiberIds.Contains(i)) continue;
            fiberObjects[i].DeactivateFiber();
        }
    }

    private void ParseAndAddFibersAsset()
    {
        string[] linesIndexes = fibersLinesIndicesAsset.text.Split('\n');
        int nbFibers = int.Parse(linesIndexes[0]);

        for (int i = 0; i < nbFibers; ++i)
        {
            string[] splitLineIndexes = linesIndexes[i + 1].Split(' ');
            var fiberId = int.Parse(splitLineIndexes[0]);
            
            // check if the object is among the meshes
            GameObject fiberObject = GameObject.Find(fiberNamePrefix + fiberId);
            if (fiberObject is null)
            {
                Debug.LogWarning("Fiber with id " + fiberId + " not found.");
                continue;
            }
            
            // initialize the material for deactivated fibers
            FiberBehavior fiber = fiberObject.AddComponent<FiberBehavior>();
            fiber.Initialize(fiberMaterial);
            fiberObject.transform.parent = transform;
            
            fiberObjects.Add(fiber);
        }
    }
    
    
    private void OnDestroy()
    {
        receiver?.Close();
        receiver = null;
    }


}
