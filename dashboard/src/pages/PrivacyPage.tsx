export default function PrivacyPage() {
  return (
    <div className="layout">
      <section className="card reveal visible">
        <h2>Privacy policy</h2>
        <p>Resonance stores robot place records on your own backend and in this browser local storage for the API address and search history.</p>
        <h3 style={{ fontSize: 13 }}>What stays local</h3>
        <ul>
          <li>Place vectors, poses, and notes stay in edge memory until you push.</li>
          <li>Dashboard search history stays in this browser only.</li>
        </ul>
        <h3 style={{ fontSize: 13 }}>What is sent</h3>
        <ul>
          <li>API calls go to the backend address shown in the header.</li>
          <li>Push to cloud sends ranked places to your Qdrant Server URL.</li>
        </ul>
        <p>Contact the operator of your deployment to delete stored places.</p>
      </section>
    </div>
  );
}
